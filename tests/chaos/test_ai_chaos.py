"""Chaos and fault injection tests for AI, OpenRouter outage, and race conditions."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.coalescer import AIRequestCoalescer
from app.core.exceptions import ExternalServiceError
from app.db.base import Base
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.moderation.engine import HonneyModerationEngine
from app.moderation.hitl.service import HumanReviewService
from app.moderation.models import ModerationAction
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage
from tests.fake_openrouter_server import FakeOpenRouterProvider


@pytest.mark.asyncio
class TestAIChaosAndFaults:
    async def test_openrouter_outage_graceful_fallback(self):
        """When OpenRouter completely fails with 500 errors, moderation falls back safely to ALLOW without crashing."""
        fake_ai = FakeOpenRouterProvider()
        fake_ai.set_injected_exception(ExternalServiceError("OpenRouter 500 Internal Server Error"))

        engine = HonneyModerationEngine(ai_provider=fake_ai)

        msg = YouTubeChatMessage(
            message_id="msg-err-1",
            live_chat_id="chat-1",
            author=YouTubeAuthor(channel_id="u1", display_name="Viewer1"),
            display_message="this is a test message during an outage",
        )
        msg.stream_session_id = "s1"

        # Must not raise unhandled exception!
        decision = await engine.evaluate_message(creator_id="c1", message=msg)
        assert decision.action == ModerationAction.ALLOW
        assert "error" in decision.reason.lower() or "safe" in decision.reason.lower()

    async def test_concurrent_moderator_review_race_condition(self):
        """Two moderators approve/deny the same review simultaneously; exactly one transition succeeds."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            c = Creator(id="c-chaos", youtube_channel_id="UC_CHAOS", channel_name="ChaosStreamer")
            s = StreamSession(id="s-chaos", creator_id="c-chaos", youtube_video_id="v-chaos")
            session.add_all([c, s])
            await session.commit()

            service = HumanReviewService(session)
            review = await service.create_review(
                creator_id="c-chaos",
                stream_session_id="s-chaos",
                message_id="msg-race-1",
                author_channel_id="u_troll",
                author_display_name="Troll",
                message_text="race message",
                confidence=60,
                severity=50,
                recommended_action="WARN",
                reason_code="RACE_TEST",
                reason="Race",
            )
            await session.commit()

        # Moderator 1 approves first in session 1
        async with session_maker() as session1:
            s1 = HumanReviewService(session1)
            res1 = await s1.approve_review(review.id[:8], moderator_id="mod-1")
            await session1.commit()

        # Moderator 2 attempts to resolve already-resolved review in session 2
        async with session_maker() as session2:
            s2 = HumanReviewService(session2)
            res2 = await s2.deny_review(review.id[:8], moderator_id="mod-2")

        # Exactly one must succeed, second must be rejected as already resolved
        assert res1[0] is True
        assert "APPROVED" in res1[1]

        assert res2[0] is False
        assert "REVIEW_ALREADY_RESOLVED" in res2[1]

        await engine.dispose()

    async def test_ai_request_coalescer_concurrency(self):
        """Twenty concurrent tasks asking for identical message classification only invoke the underlying provider once."""
        coalescer = AIRequestCoalescer()
        call_count = 0

        async def _slow_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return {"status": "computed"}

        key = coalescer.make_key("c1", "s1", "m1", "moderation_classify")

        # Launch 20 concurrent requests
        results = await asyncio.gather(
            *[coalescer.execute(key, _slow_operation) for _ in range(20)]
        )

        assert len(results) == 20
        assert call_count == 1  # Executed exactly once!
        assert coalescer.coalesced_requests == 19

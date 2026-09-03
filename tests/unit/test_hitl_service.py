"""Unit tests for HumanReviewService, TTL expiration, and atomic state transitions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.moderation.hitl.service import HumanReviewService
from app.moderation.hitl.sink import ReviewNotificationSink


class MockReviewSink(ReviewNotificationSink):
    def __init__(self):
        self.dispatched_reviews = []

    async def notify_review_created(self, review, ttl_seconds=60):
        self.dispatched_reviews.append(review)
        return True


@pytest.mark.asyncio
class TestHumanReviewService:
    @pytest.fixture
    async def async_session(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            # Seed test creator and stream session
            c = Creator(
                id="creator-test-1", youtube_channel_id="UC123", channel_name="TestStreamer"
            )
            s = StreamSession(
                id="stream-test-1", creator_id="creator-test-1", youtube_video_id="vid-1"
            )
            session.add_all([c, s])
            await session.commit()
            yield session

        await engine.dispose()

    async def test_create_and_approve_review(self, async_session: AsyncSession):
        sink = MockReviewSink()
        service = HumanReviewService(async_session, sink=sink)

        review = await service.create_review(
            creator_id="creator-test-1",
            stream_session_id="stream-test-1",
            message_id="msg-101",
            author_channel_id="user-1",
            author_display_name="TrollUser",
            message_text="chup ho ja bhai",
            confidence=60,
            severity=50,
            recommended_action="WARN",
            reason_code="AMBIGUOUS_BANTER",
            reason="Ambiguous banter",
            ttl_seconds=120,
        )

        assert review.status == "PENDING"
        assert len(sink.dispatched_reviews) == 1

        # Approve review
        success, reason = await service.approve_review(
            review_id_prefix=review.id[:8],
            moderator_id="mod-sarthak",
        )
        assert success is True
        assert "APPROVED" in reason
        assert review.status == "APPROVED"

    async def test_deny_review(self, async_session: AsyncSession):
        sink = MockReviewSink()
        service = HumanReviewService(async_session, sink=sink)

        review = await service.create_review(
            creator_id="creator-test-1",
            stream_session_id="stream-test-1",
            message_id="msg-102",
            author_channel_id="user-2",
            author_display_name="FriendlyUser",
            message_text="stream is a bit laggy",
            confidence=50,
            severity=30,
            recommended_action="WARN",
            reason_code="BORDERLINE",
            reason="Critique",
            ttl_seconds=120,
        )

        success, reason = await service.deny_review(
            review_id_prefix=review.id[:8],
            moderator_id="mod-sarthak",
        )
        assert success is True
        assert "DENIED" in reason
        assert review.status == "DENIED"

    async def test_expired_review_rejects_destructive_action(self, async_session: AsyncSession):
        sink = MockReviewSink()
        service = HumanReviewService(async_session, sink=sink)

        review = await service.create_review(
            creator_id="creator-test-1",
            stream_session_id="stream-test-1",
            message_id="msg-103",
            author_channel_id="user-3",
            author_display_name="LateUser",
            message_text="testing expire",
            confidence=70,
            severity=60,
            recommended_action="TIMEOUT",
            reason_code="EXPIRE_TEST",
            reason="Test",
            ttl_seconds=1,  # Short TTL
        )

        # Fast-forward review expiration manually in DB
        review.expires_at = datetime.now(UTC) - timedelta(seconds=10)
        await async_session.commit()

        # Attempting to approve an expired review MUST fail safely!
        success, reason = await service.approve_review(
            review_id_prefix=review.id[:8],
            moderator_id="mod-late",
        )
        assert success is False
        assert "REVIEW_EXPIRED_NO_ACTION" in reason

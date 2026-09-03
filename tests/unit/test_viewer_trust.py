"""Unit tests for ViewerTrustRepository and TrustService modifier logic."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.creator import Creator
from app.moderation.models import ModerationAction, ModerationDecision, ModerationLayer
from app.moderation.trust import TrustService


@pytest.mark.asyncio
class TestTrustService:
    @pytest.fixture
    async def async_session(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            c = Creator(
                id="creator-trust-1", youtube_channel_id="UC_TRUST", channel_name="TrustStreamer"
            )
            session.add(c)
            await session.commit()
            yield session

        await engine.dispose()

    async def test_initial_trust_score(self, async_session: AsyncSession):
        service = TrustService(async_session)
        score = await service.get_trust_score(
            creator_id="creator-trust-1", viewer_channel_id="viewer-1", display_name="LoyalViewer"
        )
        assert score == 50  # Default initial trust

    async def test_positive_interaction_increments_trust(self, async_session: AsyncSession):
        service = TrustService(async_session)
        await service.record_positive_interaction(
            creator_id="creator-trust-1", viewer_channel_id="viewer-2", display_name="ActiveViewer"
        )
        score = await service.get_trust_score(
            creator_id="creator-trust-1", viewer_channel_id="viewer-2", display_name="ActiveViewer"
        )
        assert score == 51

    async def test_trust_modifier_downgrades_mild_infraction_for_high_trust(
        self, async_session: AsyncSession
    ):
        service = TrustService(async_session)
        decision = ModerationDecision(
            action=ModerationAction.TIMEOUT,
            layer=ModerationLayer.LAYER_3_SHORT_TIMEOUT,
            confidence_score=0.91,
            reason="Borderline comment",
        )
        # Trust score 85 (High trust)
        modified = service.apply_trust_modifier(decision, trust_score=85)
        assert modified.action == ModerationAction.DELETE
        assert modified.layer == ModerationLayer.LAYER_2_WARNING_AND_DELETE
        assert "HIGH_TRUST_DOWNGRADE" in modified.matched_rules

    async def test_trust_never_overrides_extreme_ban(self):
        # Invariant: Layer 5 BAN must NEVER be softened by high trust
        service = TrustService(None)  # No DB needed for pure logic method
        ban_decision = ModerationDecision(
            action=ModerationAction.BAN,
            layer=ModerationLayer.LAYER_5_HIDE_BAN,
            confidence_score=1.0,
            reason="Violent threat",
        )
        modified = service.apply_trust_modifier(ban_decision, trust_score=100)
        assert modified.action == ModerationAction.BAN
        assert modified.layer == ModerationLayer.LAYER_5_HIDE_BAN

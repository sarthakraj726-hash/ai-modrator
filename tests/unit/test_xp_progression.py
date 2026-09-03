"""Unit tests for deterministic XP progression and multi-layer anti-farming defenses."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.repositories.engagement_repo import EngagementRepository
from app.engagement.xp import AntiFarmingGuard, XPManager


@pytest.fixture
async def xp_creator(db_session: AsyncSession) -> Creator:
    creator = Creator(
        id="c-xp-1",
        youtube_channel_id="UC_xp_1",
        channel_name="XP Streamer",
    )
    db_session.add(creator)
    await db_session.flush()
    return creator


def test_level_progression_curve():
    mgr = XPManager(base_xp=100, multiplier=1.5)

    assert mgr.calculate_level_from_xp(0) == 1
    assert mgr.calculate_level_from_xp(50) == 1
    # Level 2 reached at 100 XP
    assert mgr.calculate_level_from_xp(100) == 2
    # Level 3 requires step for level 2: 100 * (2^1.5) ≈ 282 -> cumulative ~382
    assert mgr.calculate_level_from_xp(385) == 3


def test_anti_farming_content_filter():
    guard = AntiFarmingGuard(min_message_length=4)

    # Valid chat
    valid, reason = guard.is_message_meaningful("That was an epic clutch!")
    assert valid is True

    # Too short
    valid, reason = guard.is_message_meaningful("hi")
    assert valid is False
    assert reason == "MESSAGE_TOO_SHORT"

    # Repeated characters
    valid, reason = guard.is_message_meaningful("aaaaaaaaaa")
    assert valid is False
    assert reason == "REPETITIVE_CHARACTERS"

    # Single-word repetitive spam
    valid, reason = guard.is_message_meaningful("lol lol lol lol")
    assert valid is False
    assert reason == "REPETITIVE_WORD_SPAM"

    # Emoji only
    valid, reason = guard.is_message_meaningful("🔥🔥❤️")
    assert valid is False
    assert reason == "EMOJI_ONLY"


def test_anti_farming_cooldown_and_burst():
    guard = AntiFarmingGuard(cooldown_seconds=10, max_daily_xp=100)
    creator_id = "c_farm"
    viewer_id = "v_spammer"

    # First award allowed
    allowed, reason = guard.can_award_xp(creator_id, viewer_id, 15)
    assert allowed is True
    guard.record_award(creator_id, viewer_id, 15)

    # Immediate second award blocked by cooldown
    allowed, reason = guard.can_award_xp(creator_id, viewer_id, 15)
    assert allowed is False
    assert "COOLDOWN_ACTIVE" in reason


@pytest.mark.asyncio
async def test_process_chat_message_and_level_up(db_session: AsyncSession, xp_creator: Creator):
    guard = AntiFarmingGuard(cooldown_seconds=0)  # zero cooldown for direct progression test
    mgr = XPManager(base_xp=100, anti_farming=guard)

    # Message 1: 15 XP awarded
    awarded, reason, total_xp, leveled_up = await mgr.process_chat_message(
        session=db_session,
        creator_id=xp_creator.id,
        viewer_channel_id="v_dan",
        display_name="Dan",
        message_text="Great stream today Honney!",
        base_reward=50,
    )
    assert awarded is True
    assert total_xp == 50
    assert leveled_up is False

    # Message 2: +60 XP -> total 110 XP -> Level 2 reached!
    awarded, reason, total_xp, leveled_up = await mgr.process_chat_message(
        session=db_session,
        creator_id=xp_creator.id,
        viewer_channel_id="v_dan",
        display_name="Dan",
        message_text="Let us defeat the final boss now!",
        base_reward=60,
    )
    assert awarded is True
    assert total_xp == 110
    assert leveled_up is True

    # Verify database profile state
    repo = EngagementRepository(db_session)
    profile = await repo.get_by_viewer(xp_creator.id, "v_dan")
    assert profile.total_xp == 110
    assert profile.level == 2
    assert profile.messages_count == 2

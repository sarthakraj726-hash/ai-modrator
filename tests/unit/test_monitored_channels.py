"""Unit tests for MonitoredChannel database model, repository, and identifier verification."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidArgumentError
from app.db.models.creator import Creator
from app.db.models.monitored_channel import MonitoredChannel
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.monitored_channel_repo import MonitoredChannelRepository
from app.youtube.channel_resolver import ChannelIdentifierResolver


@pytest.mark.asyncio
async def test_monitored_channel_persistence_and_unique_constraint(db_session: AsyncSession):
    """Verify MonitoredChannel persists cleanly and enforces (creator_id, youtube_channel_id) uniqueness."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-mon-test-1",
        youtube_channel_id="UC_test_creator_1",
        channel_name="Monitored Creator 1",
    )
    await creator_repo.create(creator)

    mon_repo = MonitoredChannelRepository(db_session)
    channel = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id="UC1111111111111111111111",
        channel_name="Verified Channel A",
        channel_handle="@ChannelA",
        auto_join_enabled=True,
    )
    saved = await mon_repo.create(channel)
    assert saved.id is not None
    assert saved.youtube_channel_id == "UC1111111111111111111111"
    assert saved.auto_join_enabled is True
    assert saved.enabled is True

    # Duplicate insertion for same creator and channel ID must violate unique constraint
    dup = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id="UC1111111111111111111111",
        channel_name="Duplicate A",
    )
    with pytest.raises(IntegrityError):
        await mon_repo.create(dup)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_monitored_channel_repository_queries_and_status(db_session: AsyncSession):
    """Verify repository methods for active listing and updating check status."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-mon-test-2",
        youtube_channel_id="UC_test_creator_2",
        channel_name="Monitored Creator 2",
    )
    await creator_repo.create(creator)

    mon_repo = MonitoredChannelRepository(db_session)
    ch1 = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id="UC2222222222222222222222",
        channel_name="Channel Two",
        enabled=True,
        auto_join_enabled=True,
    )
    ch2 = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id="UC3333333333333333333333",
        channel_name="Channel Three (Disabled)",
        enabled=False,
        auto_join_enabled=True,
    )
    await mon_repo.create(ch1)
    await mon_repo.create(ch2)

    # Active listing should only include enabled channels
    active = await mon_repo.list_all_active()
    active_ids = [c.youtube_channel_id for c in active]
    assert "UC2222222222222222222222" in active_ids
    assert "UC3333333333333333333333" not in active_ids

    # Update check status with live detection
    now = datetime.now(UTC)
    updated = await mon_repo.update_check_status(
        channel_id=ch1.id,
        last_checked_at=now,
        is_live=True,
        video_id="live_vid_999",
        stream_session_id="session_xyz_123",
    )
    assert updated is not None
    assert updated.last_seen_video_id == "live_vid_999"
    assert updated.last_connected_stream_session_id == "session_xyz_123"
    assert updated.last_seen_live_at is not None


@pytest.mark.asyncio
async def test_channel_identifier_verification():
    """Verify ChannelIdentifierResolver correctly parses and verifies UCIDs, handles, and URLs."""
    # 1. Direct UC ID
    res1 = await ChannelIdentifierResolver.verify_channel("UC4444444444444444444444")
    assert res1.channel_id == "UC4444444444444444444444"
    assert res1.verification_status == "VERIFIED"

    # 2. Direct @Handle
    res2 = await ChannelIdentifierResolver.verify_channel("@CoolStreamer")
    assert res2.handle == "@CoolStreamer"
    assert res2.channel_id.startswith("UC")

    # 3. Channel URL
    res3 = await ChannelIdentifierResolver.verify_channel("https://www.youtube.com/channel/UC5555555555555555555555")
    assert res3.channel_id == "UC5555555555555555555555"

    # 4. Invalid input format
    with pytest.raises(InvalidArgumentError):
        await ChannelIdentifierResolver.verify_channel("not-a-valid-youtube-channel-id")

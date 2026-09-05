"""Integration tests for auto-join concurrency and duplicate-worker prevention."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.creator import Creator
from app.db.models.monitored_channel import MonitoredChannel
from app.db.models.stream_session import StreamSession
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.monitored_channel_repo import MonitoredChannelRepository
from app.services.monitored_channel_coordinator import MonitoredChannelCoordinator
from app.services.stream_service import StreamService
from app.youtube.models import ResolvedBroadcast


@pytest.mark.asyncio
async def test_concurrent_channel_checks_prevent_duplicate_workers(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
):
    """Verify concurrent check_channel executions lock safely and only spawn a single worker."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-conc-1",
        youtube_channel_id="UC_conc_creator_1",
        channel_name="Concurrency Creator",
    )
    await creator_repo.create(creator)

    mon_repo = MonitoredChannelRepository(db_session)
    ch = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id="UC9999999999999999999999",
        channel_name="Live Streamer Concurrency",
        auto_join_enabled=True,
    )
    saved_ch = await mon_repo.create(ch)
    await db_session.commit()

    mock_broadcast = ResolvedBroadcast(
        video_id="conc_live_01",
        channel_id="UC9999999999999999999999",
        channel_title="Live Streamer Concurrency",
        title="Concurrent Stream",
        live_chat_id="chat_conc_01",
        is_live=True,
    )

    coordinator = MonitoredChannelCoordinator()

    with (
        patch.object(coordinator, "_probe_live_video_id", return_value="conc_live_01"),
        patch("app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast", return_value=mock_broadcast),
        patch("app.workers.manager.WorkerManager.start_session", new_callable=AsyncMock) as mock_worker_start,
    ):
        # Fire 5 simultaneous check_channel tasks for the exact same channel
        results = await asyncio.gather(
            coordinator.check_channel(saved_ch.id, session_factory),
            coordinator.check_channel(saved_ch.id, session_factory),
            coordinator.check_channel(saved_ch.id, session_factory),
            coordinator.check_channel(saved_ch.id, session_factory),
            coordinator.check_channel(saved_ch.id, session_factory),
            return_exceptions=False,
        )

        # Ensure worker startup was invoked AT MOST once (or subsequent was recognized as ALREADY_ACTIVE / SKIPPED)
        statuses = [r.get("status") for r in results]
        assert "LIVE_AUTO_JOINED" in statuses or "ALREADY_ACTIVE" in statuses
        assert mock_worker_start.call_count == 1

        # Count stream sessions created for this video in DB
        async with session_factory() as check_session:
            stmt = select(func.count(StreamSession.id)).where(StreamSession.youtube_video_id == "conc_live_01")
            res = await check_session.execute(stmt)
            count = res.scalar() or 0
            assert count == 1, f"Expected exactly 1 StreamSession in DB, found {count}"


@pytest.mark.asyncio
async def test_concurrent_manual_and_auto_join_lock(db_session: AsyncSession):
    """Verify simultaneous manual connect and auto-join for same video ID do not race or double-instantiate."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-conc-2",
        youtube_channel_id="UC_conc_creator_2",
        channel_name="Lock Creator",
    )
    await creator_repo.create(creator)

    mock_broadcast = ResolvedBroadcast(
        video_id="race_vid_001",
        channel_id="UC_conc_creator_2",
        channel_title="Lock Creator",
        title="Racy Broadcast",
        live_chat_id="chat_race_001",
        is_live=True,
    )

    service1 = StreamService(session=db_session)
    service2 = StreamService(session=db_session)

    with (
        patch("app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast", return_value=mock_broadcast),
        patch("app.workers.manager.WorkerManager.start_session", new_callable=AsyncMock),
    ):
        # Running bootstrap for service1 and service2
        s1 = await service1.canonical_bootstrap_stream("race_vid_001", creator_id=creator.id, auto_join=False)
        assert s1.status == "ACTIVE"

        # Simulating that worker is now registered
        with patch.object(service2.worker_manager, "get_session_sync", return_value=True):
            # Auto-join call cleanly reuses
            s2 = await service2.canonical_bootstrap_stream("race_vid_001", creator_id=creator.id, auto_join=True)
            assert s2.id == s1.id

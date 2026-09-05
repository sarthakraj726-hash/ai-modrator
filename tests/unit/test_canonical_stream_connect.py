"""Unit tests for canonical stream bootstrap pipeline and structured error handling."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateStreamConnectionError,
    EntityNotFoundError,
    LiveChatUnavailableError,
    StreamNotLiveError,
    VideoNotFoundError,
)
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.db.repositories.creator_repo import CreatorRepository
from app.services.stream_service import StreamService
from app.youtube.models import ResolvedBroadcast


@pytest.mark.asyncio
async def test_canonical_bootstrap_success(db_session: AsyncSession):
    """Verify canonical bootstrap transitions to ACTIVE and launches worker session cleanly."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-canon-1",
        youtube_channel_id="UC_canon_1",
        channel_name="Canonical Creator",
    )
    await creator_repo.create(creator)

    mock_broadcast = ResolvedBroadcast(
        video_id="canon_vid_01",
        channel_id="UC_canon_1",
        channel_title="Canonical Creator",
        title="Live Coding Stream",
        live_chat_id="chat_canon_01",
        is_live=True,
    )

    with (
        patch("app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast", return_value=mock_broadcast),
        patch("app.workers.manager.WorkerManager.start_session", new_callable=AsyncMock) as mock_start,
    ):
        service = StreamService(session=db_session)
        session = await service.canonical_bootstrap_stream(
            url_or_video_id="canon_vid_01",
            creator_id=creator.id,
            actor_id="TEST_ADMIN",
        )

        assert session is not None
        assert session.status == StreamStatus.ACTIVE.value
        assert session.youtube_video_id == "canon_vid_01"
        assert session.youtube_live_chat_id == "chat_canon_01"
        mock_start.assert_awaited_once_with(
            session_id=session.id,
            creator_id=creator.id,
            video_id="canon_vid_01",
            live_chat_id="chat_canon_01",
        )


@pytest.mark.asyncio
async def test_canonical_bootstrap_not_live_error(db_session: AsyncSession):
    """Verify bootstrap raises StreamNotLiveError with structured code when stream is not live."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-canon-2",
        youtube_channel_id="UC_canon_2",
        channel_name="Creator Two",
    )
    await creator_repo.create(creator)

    mock_broadcast = ResolvedBroadcast(
        video_id="offline_vid_2",
        channel_id="UC_canon_2",
        title="Recorded Video",
        is_live=False,
        live_chat_id="chat_offline",
    )

    with (
        patch("app.core.config.Settings.is_testing", False),
        patch("app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast", return_value=mock_broadcast),
    ):
        service = StreamService(session=db_session)
        with pytest.raises(StreamNotLiveError) as exc_info:
            await service.canonical_bootstrap_stream(
                url_or_video_id="offline_vid_2",
                creator_id=creator.id,
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.details.get("error_code") == "STREAM_NOT_LIVE"


@pytest.mark.asyncio
async def test_canonical_bootstrap_video_not_found(db_session: AsyncSession):
    """Verify bootstrap raises VideoNotFoundError when broadcast cannot be resolved."""
    with patch(
        "app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast",
        side_effect=EntityNotFoundError("YouTubeVideo", "nonexist_vid"),
    ):
        service = StreamService(session=db_session)
        with pytest.raises(VideoNotFoundError) as exc_info:
            await service.canonical_bootstrap_stream(
                url_or_video_id="nonexist_vid",
            )
        assert exc_info.value.status_code == 404
        assert exc_info.value.details.get("error_code") == "VIDEO_NOT_FOUND"


@pytest.mark.asyncio
async def test_canonical_bootstrap_live_chat_unavailable(db_session: AsyncSession):
    """Verify bootstrap raises LiveChatUnavailableError when broadcast lacks active chat ID."""
    mock_broadcast = ResolvedBroadcast(
        video_id="nochat_vid_1",
        channel_id="UC_nochat",
        is_live=True,
        live_chat_id=None,
    )
    with (
        patch("app.core.config.Settings.is_testing", False),
        patch("app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast", return_value=mock_broadcast),
    ):
        service = StreamService(session=db_session)
        with pytest.raises(LiveChatUnavailableError) as exc_info:
            await service.canonical_bootstrap_stream(
                url_or_video_id="nochat_vid_1",
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.details.get("error_code") == "LIVE_CHAT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_canonical_bootstrap_duplicate_and_autojoin_reuse(db_session: AsyncSession):
    """Verify manual bootstrap rejects active duplicate, while auto_join safely reuses existing session."""
    creator_repo = CreatorRepository(db_session)
    creator = Creator(
        id="c-canon-dup",
        youtube_channel_id="UC_canon_dup",
        channel_name="Dup Creator",
    )
    await creator_repo.create(creator)

    # Pre-existing active session
    active_session = StreamSession(
        id="sess-active-dup-01",
        creator_id=creator.id,
        youtube_video_id="dup_test_vid",
        youtube_live_chat_id="chat_dup",
        status=StreamStatus.ACTIVE.value,
    )
    db_session.add(active_session)
    await db_session.flush()

    service = StreamService(session=db_session)

    # Mock that worker session exists in WorkerManager
    with patch.object(service.worker_manager, "get_session_sync", return_value=True):
        # 1. Manual connect raises DuplicateStreamConnectionError
        with pytest.raises(DuplicateStreamConnectionError) as exc_info:
            await service.canonical_bootstrap_stream(
                url_or_video_id="dup_test_vid",
                creator_id=creator.id,
                auto_join=False,
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.details.get("error_code") == "DUPLICATE_CONNECTION"

        # 2. Auto-join safely returns existing active session without error
        reused = await service.canonical_bootstrap_stream(
            url_or_video_id="dup_test_vid",
            creator_id=creator.id,
            auto_join=True,
        )
        assert reused.id == active_session.id

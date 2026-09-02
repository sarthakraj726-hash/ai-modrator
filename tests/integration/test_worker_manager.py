"""Integration tests for WorkerManager supervision and lifecycle controls."""

import asyncio

import pytest

from app.workers.manager import WorkerManager
from app.workers.session import WorkerState
from app.youtube.client import YouTubeClient
from app.youtube.models import YouTubeChatPage, YouTubeStreamInfo


class MockYouTubeClient(YouTubeClient):
    """Mock YouTube client returning synthetic stream info and chat messages."""

    async def resolve_stream_info(self, video_id: str) -> YouTubeStreamInfo:
        return YouTubeStreamInfo(
            video_id=video_id,
            channel_id="UC_MOCK",
            title=f"Stream {video_id}",
            live_chat_id=f"chat_{video_id}",
            is_live=True,
        )

    async def get_live_chat_messages(
        self, live_chat_id: str, page_token: str | None = None
    ) -> YouTubeChatPage:
        return YouTubeChatPage(
            messages=[],
            next_page_token="next_page",
            polling_interval_millis=100,  # Fast 100ms polling for test
        )


@pytest.mark.asyncio
async def test_worker_manager_session_lifecycle():
    mock_client = MockYouTubeClient()
    manager = WorkerManager(youtube_client=mock_client)

    # 1. Start session
    session = await manager.start_session(
        session_id="session-1",
        creator_id="creator-1",
        video_id="video-1",
    )
    assert session.session_id == "session-1"
    assert session.state in (WorkerState.STARTING, WorkerState.RUNNING)

    await asyncio.sleep(0.15)
    assert session.state == WorkerState.RUNNING
    assert await manager.get_active_count() == 1

    # 2. Get session
    retrieved = await manager.get_session("session-1")
    assert retrieved == session

    # 3. List sessions
    sessions_list = await manager.list_sessions()
    assert len(sessions_list) == 1
    assert sessions_list[0]["video_id"] == "video-1"

    # 4. Stop session
    await manager.stop_session("session-1")
    assert session.state == WorkerState.STOPPED
    assert await manager.get_active_count() == 0

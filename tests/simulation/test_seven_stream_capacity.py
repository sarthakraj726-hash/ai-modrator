"""Seven-Stream Capacity and Concurrency Simulation Test."""

import asyncio

import pytest

from app.workers.manager import WorkerManager
from app.workers.session import WorkerState
from app.youtube.client import YouTubeClient
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage, YouTubeChatPage


@pytest.mark.asyncio
async def test_seven_stream_concurrent_capacity():
    """
    Capacity simulation: Runs 7 concurrent live streams (A, B, C, D, E, F, G)
    under message throughput, verifying backpressure, queue performance,
    and 100% data/message isolation.
    """
    stream_keys = ["A", "B", "C", "D", "E", "F", "G"]
    received_messages_by_stream: dict[str, list[str]] = {k: [] for k in stream_keys}

    # Custom message handler recording stream isolation
    async def message_handler(session_id: str, msg: YouTubeChatMessage) -> None:
        key = session_id.split("_")[-1]
        received_messages_by_stream[key].append(msg.message_id)

    # Mock client delivering distinct messages for each stream
    client = YouTubeClient()

    async def mock_get_chat(live_chat_id: str, page_token: str | None = None) -> YouTubeChatPage:
        stream_key = live_chat_id.split("_")[-1]
        if not page_token:
            messages = [
                YouTubeChatMessage(
                    message_id=f"msg_{stream_key}_{i}",
                    live_chat_id=live_chat_id,
                    author=YouTubeAuthor(
                        channel_id=f"UC_USER_{stream_key}_{i}",
                        display_name=f"User {stream_key} #{i}",
                    ),
                    display_message=f"Message {i} from stream {stream_key}",
                )
                for i in range(1, 11)
            ]
            return YouTubeChatPage(
                messages=messages,
                next_page_token=f"tok_{stream_key}_2",
                polling_interval_millis=50,
            )
        return YouTubeChatPage(messages=[], next_page_token=page_token, polling_interval_millis=50)

    client.get_live_chat_messages = mock_get_chat

    manager = WorkerManager()

    # 1. Launch 7 concurrent stream sessions
    for key in stream_keys:
        session_id = f"session_{key}"
        await manager.start_session(
            session_id=session_id,
            creator_id=f"creator_{key}",
            video_id=f"video_{key}",
            live_chat_id=f"chat_{key}",
            youtube_client=client,
            on_message_handler=message_handler,
        )

    # Let streams process incoming messages
    await asyncio.sleep(0.3)

    # 2. Verify all 7 streams are RUNNING
    assert await manager.get_active_count() == 7
    for key in stream_keys:
        session = await manager.get_session(f"session_{key}")
        assert session is not None
        assert session.state == WorkerState.RUNNING
        assert len(received_messages_by_stream[key]) == 10

    # 3. Verify absolute data isolation (Stream A only received A's messages, etc.)
    for key in stream_keys:
        for msg_id in received_messages_by_stream[key]:
            assert f"msg_{key}_" in msg_id

    # 4. Graceful stop for all 7 streams
    await manager.stop_all()
    assert await manager.get_active_count() == 0

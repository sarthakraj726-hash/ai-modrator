"""Mandatory Six-Stream Concurrency and Isolation Simulation Test (Phase 1 - Step 25).

Requirements:
- Simulate 6 concurrent streams (Stream A, B, C, D, E, F).
- Each has unique creator, unique session, unique chat, and private message queues.
- Verify events and messages never cross stream boundaries.
- Intentionally crash Stream C.
- Verify Streams A, B, D, E, and F remain RUNNING without interruption, while Stream C is in ERROR state.
- Restart Stream C and verify all 6 streams recover to healthy RUNNING state.
"""

import asyncio
from collections import defaultdict

import pytest

from app.workers.manager import WorkerManager
from app.workers.session import WorkerState
from app.youtube.client import YouTubeClient
from app.youtube.models import (
    YouTubeAuthor,
    YouTubeChatMessage,
    YouTubeChatPage,
    YouTubeStreamInfo,
)


class IsolatedSimulatedYouTubeClient(YouTubeClient):
    """
    Simulated YouTube client generating distinct messages per stream chat ID
    and allowing per-stream fault injection.
    """

    def __init__(self):
        self.should_crash_chat: set[str] = set()
        self.message_counters: dict[str, int] = defaultdict(int)

    async def resolve_stream_info(self, video_id: str) -> YouTubeStreamInfo:
        return YouTubeStreamInfo(
            video_id=video_id,
            channel_id=f"UC_{video_id}",
            title=f"Live Stream {video_id}",
            live_chat_id=f"chat_{video_id}",
            is_live=True,
        )

    async def get_live_chat_messages(
        self, live_chat_id: str, page_token: str | None = None
    ) -> YouTubeChatPage:
        # Check if fault injection is armed for this specific chat
        if live_chat_id in self.should_crash_chat:
            raise RuntimeError(f"FATAL INJECTED CRASH in chat: {live_chat_id}")

        self.message_counters[live_chat_id] += 1
        count = self.message_counters[live_chat_id]

        author = YouTubeAuthor(
            channel_id=f"viewer_channel_{live_chat_id}_{count}",
            display_name=f"Viewer_{live_chat_id}_{count}",
        )
        msg = YouTubeChatMessage(
            message_id=f"msg_{live_chat_id}_{count}",
            live_chat_id=live_chat_id,
            author=author,
            display_message=f"Message #{count} exclusively for {live_chat_id}",
        )

        return YouTubeChatPage(
            messages=[msg],
            next_page_token=f"token_{count + 1}",
            polling_interval_millis=50,  # 50ms interval for high-speed simulation
        )


@pytest.mark.asyncio
async def test_six_stream_concurrency_and_isolation():
    client = IsolatedSimulatedYouTubeClient()
    manager = WorkerManager(youtube_client=client)

    # Track received messages by stream session ID to verify zero cross-talk
    received_messages_by_stream: dict[str, list[YouTubeChatMessage]] = defaultdict(list)

    async def message_consumer(session_id: str, message: YouTubeChatMessage):
        received_messages_by_stream[session_id].append(message)

    manager.set_message_handler(message_consumer)

    stream_keys = ["A", "B", "C", "D", "E", "F"]
    sessions = {}

    print("\n--- Step 1: Starting 6 concurrent stream workers (A through F) ---")
    for key in stream_keys:
        session = await manager.start_session(
            session_id=f"session_{key}",
            creator_id=f"creator_{key}",
            video_id=f"video_{key}",
            live_chat_id=f"chat_video_{key}",
        )
        sessions[key] = session

    # Allow streams to poll messages concurrently
    await asyncio.sleep(0.3)

    # Verify all 6 streams are RUNNING and actively receiving their own messages
    for key in stream_keys:
        sess = sessions[key]
        assert sess.state == WorkerState.RUNNING, (
            f"Stream {key} should be RUNNING, got {sess.state}"
        )
        assert sess.messages_processed > 0, f"Stream {key} should have processed messages"
        assert len(received_messages_by_stream[f"session_{key}"]) > 0

        # Verify no message crossing: all messages in session_X must belong to chat_video_X
        for msg in received_messages_by_stream[f"session_{key}"]:
            assert msg.live_chat_id == f"chat_video_{key}"
            assert f"chat_video_{key}" in msg.display_message

    print("All 6 streams running with 100% message and state isolation.")

    # --- Step 2: Inject fatal crash exclusively into Stream C ---
    print("\n--- Step 2: Intentionally crashing Stream C ---")
    client.should_crash_chat.add("chat_video_C")

    # Wait for Stream C to hit error threshold while others keep running
    await asyncio.sleep(0.4)

    # Verify Stream C is in ERROR state
    assert sessions["C"].state == WorkerState.ERROR, (
        f"Stream C expected ERROR state, got {sessions['C'].state}"
    )
    assert sessions["C"].last_error is not None
    assert "FATAL INJECTED CRASH in chat: chat_video_C" in sessions["C"].last_error

    # Verify Streams A, B, D, E, F remain completely healthy and RUNNING!
    for key in ["A", "B", "D", "E", "F"]:
        sess = sessions[key]
        assert sess.state == WorkerState.RUNNING, (
            f"Stream {key} MUST remain RUNNING when Stream C crashes, but found {sess.state}"
        )
        assert sess.consecutive_errors == 0, f"Stream {key} should have 0 errors"

    print("Verified: Stream C crashed safely; Streams A, B, D, E, F remained in RUNNING state!")

    # --- Step 3: Clear fault injection and recover Stream C ---
    print("\n--- Step 3: Recovering and restarting Stream C ---")
    client.should_crash_chat.remove("chat_video_C")

    recovered_session_c = await manager.restart_session("session_C")
    sessions["C"] = recovered_session_c

    await asyncio.sleep(0.2)

    # Verify all 6 streams are now RUNNING
    for key in stream_keys:
        assert sessions[key].state == WorkerState.RUNNING, (
            f"Stream {key} should be RUNNING after recovery, got {sessions[key].state}"
        )

    print("All 6 streams successfully operational after Stream C recovery.")

    # Clean shutdown
    await manager.stop_all()
    for key in stream_keys:
        assert sessions[key].state == WorkerState.STOPPED

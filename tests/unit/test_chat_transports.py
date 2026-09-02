"""Unit tests for live chat transports, deduplication, and orchestrator."""

import pytest

from app.events.bus import EventBus
from app.youtube.chat.dedupe import ChatDeduplicator
from app.youtube.chat.orchestrator import CentralChatOrchestrator
from app.youtube.chat.stream_transport import StreamListLiveChatTransport
from app.youtube.client import YouTubeClient
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage
from tests.fake_youtube_server import FakeYouTubeServer


@pytest.mark.asyncio
async def test_chat_deduplication():
    dedup = ChatDeduplicator(ttl_seconds=60)
    is_dup1 = await dedup.is_duplicate_or_record("msg_test_101")
    assert is_dup1 is False  # First time: not duplicate

    is_dup2 = await dedup.is_duplicate_or_record("msg_test_101")
    assert is_dup2 is True  # Second time: duplicate!


@pytest.mark.asyncio
async def test_stream_transport_with_fake_server():
    server = FakeYouTubeServer()
    server.register_chat_messages(
        "chat_live_test",
        [
            {
                "id": "msg_s1",
                "snippet": {"type": "textMessageEvent", "displayMessage": "Streaming test"},
                "authorDetails": {"channelId": "UC_TEST", "displayName": "Tester"},
            }
        ],
    )

    client = YouTubeClient()

    # Mock _request to route through fake server
    async def mocked_request(
        endpoint,
        params,
        method_name="videos.list",
        quota_cost=None,
        http_method="GET",
        json_data=None,
    ):
        import httpx

        url = f"https://www.googleapis.com/youtube/v3/{endpoint}"
        req = httpx.Request(http_method, url, params=params)
        resp = server.handle_request(req)
        return resp.json()

    client._request = mocked_request

    transport = StreamListLiveChatTransport(live_chat_id="chat_live_test", youtube_client=client)
    await transport.connect()

    batches = []
    async for batch in transport.receive_messages():
        batches.append(batch)
        break  # Grab first batch and stop

    assert len(batches) == 1
    assert batches[0][0].message_id == "msg_s1"
    assert transport.next_page_token is not None
    await transport.close()


@pytest.mark.asyncio
async def test_orchestrator_backpressure_drop():
    bus = EventBus()
    dedup = ChatDeduplicator()
    # Small queue size of 2
    orchestrator = CentralChatOrchestrator(event_bus=bus, deduplicator=dedup, max_queue_size=2)

    msg1 = YouTubeChatMessage(
        message_id="m1",
        live_chat_id="c1",
        author=YouTubeAuthor(channel_id="u1", display_name="User 1"),
        display_message="1",
    )
    msg2 = YouTubeChatMessage(
        message_id="m2",
        live_chat_id="c1",
        author=YouTubeAuthor(channel_id="u2", display_name="User 2"),
        display_message="2",
    )
    msg3 = YouTubeChatMessage(
        message_id="m3",
        live_chat_id="c1",
        author=YouTubeAuthor(channel_id="u3", display_name="User 3"),
        display_message="3",
    )

    # Fill queue to capacity without starting consumer
    assert await orchestrator.enqueue_message(msg1) is True
    assert await orchestrator.enqueue_message(msg2) is True
    # 3rd message exceeds capacity -> dropped by backpressure
    assert await orchestrator.enqueue_message(msg3) is False
    assert orchestrator.dropped_noncritical_events == 1

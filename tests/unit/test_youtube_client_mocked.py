"""Unit tests for YouTubeClient with HTTP mocking."""

import httpx
import pytest

from app.youtube.client import YouTubeClient
from app.youtube.key_pool import ApiKeyPool
from app.youtube.quota import QuotaManager


@pytest.mark.asyncio
async def test_youtube_client_resolve_and_chat_mocked():
    qm = QuotaManager(daily_limit=100)
    pool = ApiKeyPool(keys=["AIzaSyTestKey1234567890123456789012345"])

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "videos" in url_str:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "v123",
                            "snippet": {"channelId": "UC123", "title": "Test Title"},
                            "liveStreamingDetails": {
                                "activeLiveChatId": "chat123",
                                "actualStartTime": "2026-09-02T00:00:00Z",
                            },
                        }
                    ]
                },
            )
        elif "liveChat/messages" in url_str:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "msg1",
                            "snippet": {"displayMessage": "Hello chat", "type": "textMessageEvent"},
                            "authorDetails": {"channelId": "user1", "displayName": "Bob"},
                        }
                    ],
                    "nextPageToken": "tok2",
                    "pollingIntervalMillis": 3000,
                },
            )
        return httpx.Response(404, json={"error": {"message": "Not Found"}})

    client = YouTubeClient(quota_manager=qm, key_pool=pool)

    # Override _request http client using mock transport
    async def mocked_request(endpoint, params, quota_cost, method="GET", json_data=None):
        reservation_id = await qm.reserve(units=quota_cost)
        key = await pool.get_available_key()
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            resp = await http_client.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params={**params, "key": key})
            data = resp.json()
            await qm.consume(reservation_id)
            return data

    client._request = mocked_request

    # Test resolve
    info = await client.resolve_stream_info("v123")
    assert info.video_id == "v123"
    assert info.live_chat_id == "chat123"
    assert info.is_live is True

    # Test chat messages
    page = await client.get_live_chat_messages("chat123")
    assert len(page.messages) == 1
    assert page.messages[0].display_message == "Hello chat"
    assert page.messages[0].author.display_name == "Bob"
    assert page.next_page_token == "tok2"

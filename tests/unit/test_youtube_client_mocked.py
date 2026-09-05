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
    async def mocked_request(
        endpoint,
        params,
        method_name="videos.list",
        quota_cost=None,
        http_method="GET",
        json_data=None,
        **kwargs,
    ):
        cost = quota_cost or 1
        reservation_id = await qm.reserve(units=cost)
        key = await pool.get_available_key()
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            resp = await http_client.get(
                f"https://www.googleapis.com/youtube/v3/{endpoint}", params={**params, "key": key}
            )
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


@pytest.mark.asyncio
async def test_youtube_client_insert_and_delete_message():
    qm = QuotaManager(daily_limit=1000)
    pool = ApiKeyPool(keys=["AIzaSyTestKey1234567890123456789012345"])

    posted_messages = []
    deleted_ids = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "liveChat/messages" in url_str:
            if request.method == "POST":
                import json

                body = json.loads(request.content.decode("utf-8")) if request.content else {}
                posted_messages.append(body)
                return httpx.Response(
                    200,
                    json={
                        "id": "new_msg_id_1",
                        "snippet": body.get("snippet", {}),
                    },
                )
            elif request.method == "DELETE":
                deleted_ids.append(str(request.url))
                return httpx.Response(204)
        return httpx.Response(404, json={"error": {"message": "Not Found"}})

    client = YouTubeClient(quota_manager=qm, key_pool=pool)

    async def mocked_request(
        endpoint,
        params,
        method_name="videos.list",
        quota_cost=None,
        http_method="GET",
        json_data=None,
        **kwargs,
    ):
        cost = quota_cost or 50
        reservation_id = await qm.reserve(units=cost, method=method_name)
        key = await pool.get_available_key()
        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            if http_method == "GET":
                resp = await http_client.get(
                    f"https://www.googleapis.com/youtube/v3/{endpoint}",
                    params={**params, "key": key},
                )
            else:
                resp = await http_client.request(
                    http_method,
                    f"https://www.googleapis.com/youtube/v3/{endpoint}",
                    params={**params, "key": key},
                    json=json_data,
                )
            if resp.status_code == 204:
                await qm.consume(reservation_id, method=method_name)
                return {}
            data = resp.json()
            await qm.consume(reservation_id, method=method_name)
            return data

    client._request = mocked_request

    # Test insert_live_chat_message
    res = await client.insert_live_chat_message("chat_xyz", "✨ Goddess AI is live! ✨")
    assert res["id"] == "new_msg_id_1"
    assert len(posted_messages) == 1
    assert posted_messages[0]["snippet"]["textMessageDetails"]["messageText"] == "✨ Goddess AI is live! ✨"

    # Test delete_live_chat_message
    del_res = await client.delete_live_chat_message("msg_del_123")
    assert del_res == {}
    assert len(deleted_ids) == 1

    # Test edge cases: empty chat_id or empty message
    empty_res = await client.insert_live_chat_message("", "Hello")
    assert empty_res == {}
    empty_res2 = await client.insert_live_chat_message("chat_xyz", "   ")
    assert empty_res2 == {}
    empty_del = await client.delete_live_chat_message("")
    assert empty_del == {}

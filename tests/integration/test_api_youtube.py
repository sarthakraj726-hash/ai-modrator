"""Integration tests for YouTube endpoints and URL-based stream connection."""

import pytest
from httpx import AsyncClient

from app.youtube.broadcast_resolver import get_broadcast_resolver
from app.youtube.models import ResolvedBroadcast


@pytest.mark.asyncio
async def test_youtube_diagnostics_endpoints(client: AsyncClient, admin_headers: dict[str, str]):
    # 1. /youtube/status
    resp = await client.get("/youtube/status", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"
    assert "daily_budget" in data
    assert "remaining_quota" in data

    # 2. /youtube/quota
    resp_q = await client.get("/youtube/quota", headers=admin_headers)
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert "requests_by_method" in data_q

    # 3. /youtube/keys
    resp_k = await client.get("/youtube/keys", headers=admin_headers)
    assert resp_k.status_code == 200
    data_k = resp_k.json()
    assert data_k["total_keys"] >= 1
    assert "masked_key" in data_k["keys"][0]

    # 4. /youtube/discovery/status
    resp_d = await client.get("/youtube/discovery/status", headers=admin_headers)
    assert resp_d.status_code == 200


@pytest.mark.asyncio
async def test_connect_stream_by_url(client: AsyncClient, admin_headers: dict[str, str]):
    # Mock Broadcast Resolver
    resolver = get_broadcast_resolver()

    async def mock_resolve_broadcast(vid):
        return ResolvedBroadcast(
            video_id=vid,
            channel_id="UC_API_URL_CHAN",
            channel_title="URL Streamer",
            title="Live via URL",
            live_chat_id="chat_url_live_1",
            is_live=True,
        )

    resolver.resolve_broadcast = mock_resolve_broadcast

    # 1. Connect via URL
    payload = {"youtube_live_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    resp = await client.post("/streams/connect", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["youtube_video_id"] == "dQw4w9WgXcQ"
    session_id = data["id"]

    # 2. Duplicate connect attempt should fail (409 Conflict)
    resp_dup = await client.post("/streams/connect", json=payload, headers=admin_headers)
    assert resp_dup.status_code in (400, 409)

    # 3. Disconnect
    resp_disc = await client.post(f"/streams/{session_id}/disconnect", headers=admin_headers)
    assert resp_disc.status_code == 200
    assert resp_disc.json()["status"] == "ENDED"

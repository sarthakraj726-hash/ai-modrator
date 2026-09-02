"""Integration tests for Stream Session endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_stream_connect_and_disconnect(client: AsyncClient, admin_headers: dict[str, str]):
    # 1. Register creator
    create_creator_resp = await client.post(
        "/creators",
        json={"youtube_channel_id": "UC_STREAM_CREATOR", "channel_name": "Streamer"},
        headers=admin_headers,
    )
    creator_id = create_creator_resp.json()["id"]

    # 2. Connect stream
    connect_payload = {
        "creator_id": creator_id,
        "youtube_video_id": "video_abc_123",
        "youtube_live_chat_id": "chat_xyz_789",
    }
    connect_resp = await client.post(
        "/streams/connect", json=connect_payload, headers=admin_headers
    )
    assert connect_resp.status_code == 201
    stream_data = connect_resp.json()
    session_id = stream_data["id"]
    assert stream_data["status"] == "ACTIVE"

    # 3. Get stream details
    get_stream = await client.get(f"/streams/{session_id}")
    assert get_stream.status_code == 200
    assert get_stream.json()["youtube_video_id"] == "video_abc_123"

    # 4. List active streams
    active_resp = await client.get("/streams/active")
    assert active_resp.status_code == 200
    assert any(s["id"] == session_id for s in active_resp.json())

    # 5. Disconnect stream
    disc_resp = await client.post(f"/streams/{session_id}/disconnect", headers=admin_headers)
    assert disc_resp.status_code == 200
    assert disc_resp.json()["status"] == "ENDED"

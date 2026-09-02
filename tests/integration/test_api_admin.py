"""Integration tests for Admin routes and diagnostics."""

import pytest
from httpx import AsyncClient

from app.youtube.quota import get_quota_manager


@pytest.mark.asyncio
async def test_admin_key_pool_endpoint(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.get("/admin/key-pool", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "masked_key" in data[0]
    assert "status" in data[0]


@pytest.mark.asyncio
async def test_admin_quota_endpoint(client: AsyncClient, admin_headers: dict[str, str]):
    qm = get_quota_manager()
    res = await qm.reserve(10)
    await qm.consume(res)

    resp = await client.get("/admin/quota", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["daily_limit"] == qm.daily_limit
    assert data["used"] == 10
    assert data["remaining"] == qm.daily_limit - 10


@pytest.mark.asyncio
async def test_admin_system_events_and_audits(client: AsyncClient, admin_headers: dict[str, str]):
    # Register creator to generate audit
    creator_resp = await client.post(
        "/creators",
        json={"youtube_channel_id": "UC_ADMIN_AUDIT", "channel_name": "Audit Channel"},
        headers=admin_headers,
    )
    creator_id = creator_resp.json()["id"]

    stream_resp = await client.post(
        "/streams/connect",
        json={"creator_id": creator_id, "youtube_video_id": "v_audit_1", "youtube_live_chat_id": "c_audit_1"},
        headers=admin_headers,
    )
    session_id = stream_resp.json()["id"]

    # Stream audits
    audit_resp = await client.get(f"/admin/audits/stream/{session_id}", headers=admin_headers)
    assert audit_resp.status_code == 200
    audits = audit_resp.json()
    assert len(audits) >= 1
    assert audits[0]["stream_session_id"] == session_id

    # System events
    sys_resp = await client.get("/admin/system-events", headers=admin_headers)
    assert sys_resp.status_code == 200
    assert isinstance(sys_resp.json(), list)

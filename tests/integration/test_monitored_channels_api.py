"""Integration tests for Monitored Channels REST API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator


@pytest.mark.asyncio
async def test_monitored_channels_crud_api(client: AsyncClient, db_session: AsyncSession):
    """Verify full CRUD lifecycle for monitored YouTube channels via REST API."""
    creator = Creator(
        id="c-api-test-1",
        youtube_channel_id="UC_api_creator_1",
        channel_name="API Creator One",
    )
    db_session.add(creator)
    await db_session.commit()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}

    # 1. Add and verify new monitored channel
    create_payload = {
        "identifier": "UC1234567890123456789012",
        "display_label": "Gaming Channel",
        "auto_join_enabled": True,
        "creator_id": creator.id,
    }
    res_add = await client.post(
        "/api/v1/dashboard/monitored-channels",
        headers=headers,
        json=create_payload,
    )
    assert res_add.status_code == 200
    data_add = res_add.json()
    channel_id = data_add["id"]
    assert data_add["creator_id"] == creator.id
    assert data_add["auto_join_enabled"] is True
    assert data_add["verification_status"] == "VERIFIED"

    # 2. Duplicate add returns 409 Conflict
    res_dup = await client.post(
        "/api/v1/dashboard/monitored-channels",
        headers=headers,
        json=create_payload,
    )
    assert res_dup.status_code == 409

    # 3. List monitored channels
    res_list = await client.get("/api/v1/dashboard/monitored-channels", headers=headers)
    assert res_list.status_code == 200
    channels = res_list.json()
    assert any(c["id"] == channel_id for c in channels)

    # 4. PATCH toggle auto-join off
    res_patch = await client.patch(
        f"/api/v1/dashboard/monitored-channels/{channel_id}",
        headers=headers,
        json={"auto_join_enabled": False, "display_label": "Updated Label"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["auto_join_enabled"] is False
    assert res_patch.json()["display_label"] == "Updated Label"

    # 5. POST check-now
    with patch(
        "app.services.monitored_channel_coordinator.MonitoredChannelCoordinator.check_channel",
        new_callable=AsyncMock,
        return_value={"status": "OFFLINE", "channel_id": "UC1234567890123456789012"},
    ):
        res_check = await client.post(
            f"/api/v1/dashboard/monitored-channels/{channel_id}/check-now",
            headers=headers,
            json={},
        )
        assert res_check.status_code == 200
        assert res_check.json()["status"] == "OFFLINE"

    # 6. DELETE channel
    res_del = await client.delete(
        f"/api/v1/dashboard/monitored-channels/{channel_id}",
        headers=headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "DELETED"

    # 7. Channel should no longer appear in list
    res_list_after = await client.get("/api/v1/dashboard/monitored-channels", headers=headers)
    assert not any(c["id"] == channel_id for c in res_list_after.json())

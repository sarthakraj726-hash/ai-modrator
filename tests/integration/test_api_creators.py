"""Integration tests for Creator management endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_creator_crud_flow(client: AsyncClient, admin_headers: dict[str, str]):
    # 1. Register new creator
    payload = {
        "youtube_channel_id": "UC_TEST_CHANNEL_1",
        "channel_name": "Test Gamer Channel",
        "enabled": True,
    }
    create_resp = await client.post("/creators", json=payload, headers=admin_headers)
    assert create_resp.status_code == 201
    creator_data = create_resp.json()
    creator_id = creator_data["id"]
    assert creator_data["youtube_channel_id"] == "UC_TEST_CHANNEL_1"

    # 2. Get creator by ID
    get_resp = await client.get(f"/creators/{creator_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["channel_name"] == "Test Gamer Channel"

    # 3. List creators
    list_resp = await client.get("/creators")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 4. Update creator
    patch_resp = await client.patch(
        f"/creators/{creator_id}",
        json={"channel_name": "Updated Gamer Channel"},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["channel_name"] == "Updated Gamer Channel"

    # 5. Delete creator
    del_resp = await client.delete(f"/creators/{creator_id}", headers=admin_headers)
    assert del_resp.status_code == 204

    # 6. Verify deleted
    get_after_del = await client.get(f"/creators/{creator_id}")
    assert get_after_del.status_code == 404

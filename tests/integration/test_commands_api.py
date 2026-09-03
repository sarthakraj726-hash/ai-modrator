"""Integration tests for Phase 4 REST API routes."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.session import get_db_session
from app.main import app


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_commands_and_store_rest_api(api_client: AsyncClient, db_session: AsyncSession):
    creator = Creator(
        id="c-rest-1",
        youtube_channel_id="UC_rest_1",
        channel_name="REST Streamer",
    )
    db_session.add(creator)
    await db_session.flush()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}

    # 1. Create custom command via API
    resp = await api_client.post(
        f"/api/v1/commands/{creator.id}",
        json={
            "name": "donate",
            "response": "Support us on Patreon!",
            "min_role": "VIEWER",
            "cooldown_seconds": 10,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "!donate"

    # 2. List commands via API
    resp = await api_client.get(f"/api/v1/commands/{creator.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["commands"][0]["name"] == "!donate"

    # 3. Create Store Item via API
    resp = await api_client.post(
        f"/api/v1/store/{creator.id}/items",
        json={
            "name": "Sticker",
            "description": "Virtual stream sticker",
            "price": 25,
            "stock": 50,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sticker"

    # 4. List Store Items via API
    resp = await api_client.get(f"/api/v1/store/{creator.id}/items")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1

    # 5. Admin Give Coins via API
    resp = await api_client.post(
        f"/api/v1/economy/{creator.id}/give",
        json={
            "target_viewer_id": "v_rest_winner",
            "amount": 250,
            "reason": "Tournament winner",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # 6. Check Balance via API
    resp = await api_client.get(f"/api/v1/economy/{creator.id}/balance/v_rest_winner")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 250

    # 7. Delete Command via API
    resp = await api_client.delete(f"/api/v1/commands/{creator.id}/donate", headers=headers)
    assert resp.status_code == 200

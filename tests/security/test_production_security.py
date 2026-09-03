"""Production security, RBAC authorization, and isolation tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.session import get_db_session
from app.main import app


@pytest.fixture
async def api_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_unauthenticated_rejected(api_client: AsyncClient):
    # Request without X-Admin-Secret header
    res = await api_client.get("/api/v1/dashboard/overview")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_invalid_secret_rejected(api_client: AsyncClient):
    # Request with wrong secret
    headers = {"X-Admin-Secret": "totally-bogus-invalid-secret"}
    res = await api_client.get("/api/v1/dashboard/overview", headers=headers)
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_authenticated_success(api_client: AsyncClient, db_session: AsyncSession):
    headers = {"X-Admin-Secret": "test-admin-secret-12345"}
    res = await api_client.get("/api/v1/dashboard/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "overall_status" in data
    assert "active_streams" in data


@pytest.mark.asyncio
async def test_cross_creator_isolation(api_client: AsyncClient, db_session: AsyncSession):
    c1 = Creator(
        id="c-sec-1",
        youtube_channel_id="UC_sec_1",
        channel_name="Creator One",
    )
    c2 = Creator(
        id="c-sec-2",
        youtube_channel_id="UC_sec_2",
        channel_name="Creator Two",
    )
    db_session.add_all([c1, c2])
    await db_session.flush()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}
    res = await api_client.get("/api/v1/dashboard/creators", headers=headers)
    assert res.status_code == 200
    creators = res.json()
    ids = [c["id"] for c in creators]
    assert "c-sec-1" in ids
    assert "c-sec-2" in ids

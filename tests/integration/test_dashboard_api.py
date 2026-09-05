"""Integration tests for Developer Control Center endpoints."""

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
async def test_dashboard_full_flow(api_client: AsyncClient, db_session: AsyncSession):
    creator = Creator(
        id="c-dash-1",
        youtube_channel_id="UC_dash_1",
        channel_name="Dashboard Streamer",
    )
    db_session.add(creator)
    await db_session.flush()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}

    # 1. Overview
    res = await api_client.get("/api/v1/dashboard/overview", headers=headers)
    assert res.status_code == 200
    assert res.json()["total_creators"] >= 1

    # 2. Streams List
    res = await api_client.get("/api/v1/dashboard/streams", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 3. Manual Connect Stream
    connect_payload = {"url_or_video_id": "vid_dash_test", "creator_id": "c-dash-1"}
    res = await api_client.post(
        "/api/v1/dashboard/streams/manual-connect", headers=headers, json=connect_payload
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"

    # 4. Quota
    res = await api_client.get("/api/v1/dashboard/quota", headers=headers)
    assert res.status_code == 200
    assert res.json()["budget"] > 0

    # 5. YouTube Keys
    res = await api_client.get("/api/v1/dashboard/youtube-keys", headers=headers)
    assert res.status_code == 200

    # 6. Detailed Health Endpoint
    res = await api_client.get("/health/detailed")
    assert res.status_code == 200
    assert res.json()["service"] == "goddess-ai-modrator"

    # 7. Root Web Endpoint (Browser HTML)
    res = await api_client.get("/", headers={"Accept": "text/html"})
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "GODDESS AI" in res.text

    # 8. Root API Descriptor (JSON)
    res = await api_client.get("/", headers={"Accept": "application/json"})
    assert res.status_code == 200
    assert res.json()["service"] == "Goddess AI / AI-Modrator"

    # 9. Dashboard Web View Alias
    res = await api_client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]

    # 10. Direct /api/v1/overview Alias
    res = await api_client.get("/api/v1/overview", headers=headers)
    assert res.status_code == 200
    assert res.json()["total_creators"] >= 1

    # 11. Direct /api/v1/streams Alias
    res = await api_client.get("/api/v1/streams", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 12. Bot Auth Status
    res = await api_client.get("/api/v1/dashboard/bot-auth", headers=headers)
    assert res.status_code == 200
    assert "is_authenticated" in res.json()

    # 13. Save Bot Token
    res = await api_client.post(
        "/api/v1/dashboard/bot-auth",
        headers=headers,
        json={"token": "ya29.test_access_token_12345", "is_refresh_token": False},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "SAVED"

    # 14. Verify Bot Auth Status Updated
    res = await api_client.get("/api/v1/dashboard/bot-auth", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_authenticated"] is True
    assert "ya29." in res.json()["token_preview"]

    # 15. Clear Bot Token
    res = await api_client.delete("/api/v1/dashboard/bot-auth", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CLEARED"

    # 16. Test Message Endpoint (with mocked YouTube Client insert)
    from unittest.mock import AsyncMock, patch

    with patch(
        "app.youtube.client.YouTubeClient.insert_live_chat_message",
        new_callable=AsyncMock,
        return_value={"id": "mock_msg_123"},
    ):
        res = await api_client.post(
            "/api/v1/dashboard/streams/test-message",
            headers=headers,
            json={"live_chat_id": "test_chat_id_123", "message": "Test live message"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "SENT"
        assert res.json()["response"]["id"] == "mock_msg_123"



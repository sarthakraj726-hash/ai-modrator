"""Security tests verifying RBAC enforcement and creator data isolation."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_dashboard_endpoints_require_admin_authentication(api_client: AsyncClient):
    """Verify all dashboard endpoints reject unauthenticated requests with 401/403."""
    endpoints = [
        "/api/v1/dashboard/overview",
        "/api/v1/dashboard/streams",
        "/api/v1/dashboard/quota",
        "/api/v1/dashboard/youtube-keys",
        "/api/v1/dashboard/ai",
        "/api/v1/dashboard/moderation",
        "/api/v1/dashboard/incidents",
        "/api/v1/dashboard/economy",
        "/api/v1/dashboard/audit-logs",
        "/api/v1/dashboard/feature-flags",
    ]

    for ep in endpoints:
        # Request without any credentials
        res = await api_client.get(ep)
        assert res.status_code in (401, 403), (
            f"Endpoint {ep} did not enforce auth (status: {res.status_code})"
        )

        # Request with invalid secret
        res_invalid = await api_client.get(ep, headers={"X-Admin-Secret": "wrong-secret"})
        assert res_invalid.status_code in (401, 403)

"""Integration tests for AI, Moderation, and Persona REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAIAndModerationRoutes:
    async def test_ai_status_endpoint(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get("/ai/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] in ("openrouter", "fake-openrouter")
        assert "fast_model" in data

    async def test_ai_budget_endpoint(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get("/ai/budget", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_requests_limit" in data
        assert data["daily_requests_limit"] > 0

    async def test_moderation_status_endpoint(self, client: AsyncClient, admin_headers: dict):
        resp = await client.get("/moderation/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "HEALTHY"
        assert data["hitl_enabled"] is True

    async def test_creator_persona_endpoints(self, client: AsyncClient, admin_headers: dict):
        # 1. Register creator first
        c_resp = await client.post(
            "/creators",
            headers=admin_headers,
            json={"youtube_channel_id": "UC_TEST_PERSONA", "channel_name": "PersonaStreamer"},
        )
        assert c_resp.status_code == 201
        creator_id = c_resp.json()["id"]

        # 2. Get persona settings
        p_get = await client.get(f"/creators/{creator_id}/persona", headers=admin_headers)
        assert p_get.status_code == 200
        assert p_get.json()["persona_type"] == "CO_HOST"

        # 3. Update persona settings
        p_put = await client.put(
            f"/creators/{creator_id}/persona",
            headers=admin_headers,
            json={"persona_type": "HYPE", "custom_persona_prompt": "Stay hype always!"},
        )
        assert p_put.status_code == 200
        assert p_put.json()["persona_type"] == "HYPE"
        assert p_put.json()["custom_persona_prompt"] == "Stay hype always!"

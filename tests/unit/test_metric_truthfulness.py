"""Unit tests verifying truthful metric classification without fake zeros."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_ai_and_quota_metric_truthfulness(client: AsyncClient, db_session: AsyncSession):
    """Verify metrics return explicit accuracy classifications and no fake values."""
    headers = {"X-Admin-Secret": "test-admin-secret-12345"}

    # 1. Quota Endpoint
    q_res = await client.get("/api/v1/dashboard/quota", headers=headers)
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert "accuracy" in q_data
    assert q_data["accuracy"]["budget"] == "MEASURED"
    assert q_data["accuracy"]["consumed"] == "MEASURED"
    assert q_data["accuracy"]["remaining"] == "DERIVED"

    # 2. AI Metrics Endpoint
    ai_res = await client.get("/api/v1/dashboard/ai", headers=headers)
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert "estimated_cost_usd" in ai_data  # Explicitly labeled as estimated
    assert "accuracy" in ai_data
    assert ai_data["accuracy"]["estimated_cost_usd"] == "ESTIMATED"
    assert ai_data["accuracy"]["total_requests"] == "MEASURED"

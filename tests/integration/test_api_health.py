"""Integration tests for Health check API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live_endpoint(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "live"


@pytest.mark.asyncio
async def test_health_ready_endpoint(client: AsyncClient):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "healthy"
    assert data["redis"] == "healthy"


@pytest.mark.asyncio
async def test_health_full_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "goddess-ai-modrator"
    assert "workers" in data
    assert "youtube" in data
    assert data["youtube"]["quota_daily_limit"] == 4000

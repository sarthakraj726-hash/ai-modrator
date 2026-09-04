"""Integration tests verifying production startup, fail-fast security validation, and health probe behavior."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import create_application


def test_production_negative_startup_validation(monkeypatch):
    """
    Step 15: Verify that production startup fails under invalid secret configurations:
    1. Missing ADMIN_SECRET
    2. Known development placeholder
    3. Weak ADMIN_SECRET (< 16 chars)
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")

    # 1. Missing ADMIN_SECRET
    monkeypatch.setenv("ADMIN_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError) as exc1:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc1.value)

    # 2. Known placeholder
    monkeypatch.setenv("ADMIN_SECRET", "dev-admin-secret-replace-in-production")
    get_settings.cache_clear()
    with pytest.raises(ValueError) as exc2:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc2.value)

    # 3. Weak value
    monkeypatch.setenv("ADMIN_SECRET", "weak_123")
    get_settings.cache_clear()
    with pytest.raises(ValueError) as exc3:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc3.value)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_production_positive_startup_and_health_live(monkeypatch):
    """
    Step 14 & 16: Verify that with synthetic production credentials:
    1. Settings loads and normalizes correctly.
    2. FastAPI application creates cleanly.
    3. /health/live responds with 200 OK and {"status": "live"} without requiring external services.
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "FakeProductionSecretOnlyForTests_123!")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://prod_user:prod_pass@containers-us-west-1.railway.app:5432/railway",
    )
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.APP_ENV == "production"
    assert settings.is_production is True
    assert settings.ADMIN_SECRET == "FakeProductionSecretOnlyForTests_123!"
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")

    # Create application instance under production configuration
    prod_app = create_application()
    assert prod_app is not None
    assert prod_app.title == "Goddess AI / AI-Modrator"

    # Verify /health/live probe is lightweight and responds immediately
    transport = ASGITransport(app=prod_app)
    async with AsyncClient(transport=transport, base_url="http://prodserver") as client:
        res = await client.get("/health/live")
        assert res.status_code == 200
        payload = res.json()
        assert payload["status"] == "live"

    get_settings.cache_clear()

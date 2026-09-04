"""Unit tests verifying production security, credential redaction, and APP_ENV enforcement."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.cache.redis import init_redis
from app.core.config import Settings, get_settings
from app.core.database_url import (
    normalize_database_url,
    sanitize_connection_url,
    sanitize_database_url,
    sanitize_redis_url,
)


def test_sanitize_redis_url_formats():
    """Verify all Redis URL password variations are redacted."""
    # 1. Standard user:password format
    url1 = "redis://default:SuperSecretPassword123@redis.railway.internal:6379/0"
    sanitized1 = sanitize_redis_url(url1)
    assert "SuperSecretPassword123" not in sanitized1
    assert "redis://default:***@redis.railway.internal:6379/0" == sanitized1

    # 2. Redis password-only :password format
    url2 = "redis://:AnotherSecretPassword456@redis.railway.internal:6379"
    sanitized2 = sanitize_redis_url(url2)
    assert "AnotherSecretPassword456" not in sanitized2
    assert "redis://:***@redis.railway.internal:6379" == sanitized2

    # 3. Secure TLS rediss:// format
    url3 = "rediss://admin:TlsSecret789@secure-redis.railway.internal:6380/2"
    sanitized3 = sanitize_redis_url(url3)
    assert "TlsSecret789" not in sanitized3
    assert "rediss://admin:***@secure-redis.railway.internal:6380/2" == sanitized3

    # 4. Plain URL with no credentials
    url4 = "redis://localhost:6379/0"
    assert sanitize_redis_url(url4) == "redis://localhost:6379/0"


def test_sanitize_database_url_formats():
    """Verify PostgreSQL database URLs mask passwords."""
    url = "postgresql+asyncpg://postgres:VerySecretPostgresPass@containers-us-west-1.railway.app:5432/railway"
    sanitized = sanitize_database_url(url)
    assert "VerySecretPostgresPass" not in sanitized
    assert (
        "postgresql+asyncpg://postgres:***@containers-us-west-1.railway.app:5432/railway"
        == sanitized
    )


def test_sanitize_error_message_containing_credentials():
    """Verify exception messages containing connection strings are sanitized."""
    raw_error = "ConnectionError: failed to connect to redis://default:LeakMeNow999@10.0.0.5:6379"
    sanitized = sanitize_connection_url(raw_error)
    assert "LeakMeNow999" not in sanitized
    assert "redis://default:***@10.0.0.5:6379" in sanitized


@pytest.mark.asyncio
async def test_redis_init_logging_never_exposes_credentials(caplog, monkeypatch):
    """Verify that init_redis() logs redact credentials and never leak plain secrets."""
    secret_pass = "CompromisedTestSecret999888"
    raw_url = f"redis://default:{secret_pass}@mock-redis.internal:6379/0"

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "prod-secure-token-1234567890")
    monkeypatch.setenv("REDIS_URL", raw_url)
    monkeypatch.setenv("DATABASE_URL", "postgresql://pguser:secret@mock-db.internal:5432/railway")
    get_settings.cache_clear()

    # Mock aioredis.from_url to simulate successful connection
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)

    with patch("redis.asyncio.from_url", return_value=mock_client), caplog.at_level(logging.INFO):
        await init_redis()

    # Ensure secret is nowhere in captured logs
    assert secret_pass not in caplog.text
    # Ensure sanitized message is present
    assert "Connected to Redis at redis://default:***@mock-redis.internal:6379/0" in caplog.text

    get_settings.cache_clear()


def test_app_env_production_validation(monkeypatch):
    """Verify APP_ENV=production enforces production constraints and fails on invalid configurations."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "prod-secure-token-1234567890")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://pguser:pass123@containers-us-west-1.railway.app:5432/railway",
    )
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.APP_ENV == "production"
    assert settings.is_production is True
    assert settings.is_testing is False
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")

    # In production, invalid scheme must fail fast without leaking password
    with pytest.raises(ValueError) as excinfo:
        normalize_database_url("sqlite+aiosqlite:///./prod.db", app_env="production")
    assert "Production DATABASE_URL must use an async PostgreSQL driver" in str(excinfo.value)

    get_settings.cache_clear()


def test_railway_environment_autodetection(monkeypatch):
    """Verify that Railway environment hints auto-detect production if APP_ENV is unset."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_SECRET", "prod-secure-token-1234567890")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://railway_user:pass@containers-us-west-1.railway.app:5432/railway",
    )
    get_settings.cache_clear()

    settings = Settings()
    assert settings.APP_ENV == "production"
    assert settings.is_production is True

    get_settings.cache_clear()


def test_production_fails_fast_on_insecure_default_admin_secret(monkeypatch):
    """Verify that production startup immediately fails if default insecure admin secrets are used."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@db.railway.internal:5432/prod",
    )
    # 1. Default dev secret must fail
    monkeypatch.setenv("ADMIN_SECRET", "dev-admin-secret-replace-in-production")
    get_settings.cache_clear()
    with pytest.raises(ValueError) as exc:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc.value)

    # 2. Generic weak password must fail
    monkeypatch.setenv("ADMIN_SECRET", "password")
    get_settings.cache_clear()
    with pytest.raises(ValueError) as exc2:
        Settings()
    assert "Production security violation" in str(exc2.value)

    get_settings.cache_clear()


def test_admin_secret_policy_development_defaults_allowed(monkeypatch):
    """Verify that development and testing environments allow default dev admin secret."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ADMIN_SECRET", "dev-admin-secret-replace-in-production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    settings = Settings()
    assert settings.APP_ENV == "development"
    assert settings.ADMIN_SECRET == "dev-admin-secret-replace-in-production"
    get_settings.cache_clear()


def test_admin_secret_policy_production_missing_secret_fails(monkeypatch):
    """Verify that production startup fails if ADMIN_SECRET is missing or empty."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")
    get_settings.cache_clear()

    with pytest.raises(ValueError) as exc:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc.value)
    get_settings.cache_clear()


def test_admin_secret_policy_production_placeholder_fails(monkeypatch):
    """Verify that production startup fails if ADMIN_SECRET uses known development placeholders."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")

    placeholders = [
        "dev-admin-secret-replace-in-production",
        "change-this-to-a-secure-random-secret-in-production",
        "admin",
        "secret",
        "password",
        "changeme",
        "12345678",
    ]
    for placeholder in placeholders:
        monkeypatch.setenv("ADMIN_SECRET", placeholder)
        get_settings.cache_clear()
        with pytest.raises(ValueError) as exc:
            Settings()
        assert "Production security violation: ADMIN_SECRET must be set" in str(exc.value)

    get_settings.cache_clear()


def test_admin_secret_policy_production_weak_secret_fails(monkeypatch):
    """Verify that production startup fails if ADMIN_SECRET is shorter than 16 characters."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")
    monkeypatch.setenv("ADMIN_SECRET", "short_weak_123")  # 14 chars
    get_settings.cache_clear()

    with pytest.raises(ValueError) as exc:
        Settings()
    assert "Production security violation: ADMIN_SECRET must be set" in str(exc.value)
    get_settings.cache_clear()


def test_admin_secret_policy_production_strong_secret_passes(monkeypatch):
    """Verify that production startup succeeds when configured with a strong synthetic secret."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")
    monkeypatch.setenv("ADMIN_SECRET", "FakeProductionSecretOnlyForTests_123!")
    get_settings.cache_clear()

    settings = Settings()
    assert settings.APP_ENV == "production"
    assert settings.ADMIN_SECRET == "FakeProductionSecretOnlyForTests_123!"
    get_settings.cache_clear()


def test_production_cors_restricts_wildcard_origins(monkeypatch):
    """Verify that in production, wildcard CORS origin ['*'] is replaced with safe origins."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "prod-super-secure-token-998877")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@db.railway.internal:5432/prod",
    )
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    get_settings.cache_clear()

    settings = Settings()
    assert settings.is_production is True
    assert "*" not in settings.CORS_ORIGINS
    assert "https://railway.app" in settings.CORS_ORIGINS

    get_settings.cache_clear()

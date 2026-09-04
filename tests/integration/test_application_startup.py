"""Integration tests for application lifespan startup, shutdown, and clean resource lifecycle without unawaited coroutines."""

import warnings

import pytest
from httpx import ASGITransport, AsyncClient

from app.cache.redis import get_redis_client, get_redis_sync
from app.core.lifecycle import lifespan
from app.main import app
from app.moderation.spam import BehavioralSpamDetector


@pytest.mark.asyncio
async def test_application_startup_and_shutdown_lifecycle():
    """
    Test application startup -> resources initialized -> health endpoints ready -> shutdown.
    Ensures zero RuntimeWarning: coroutine was never awaited.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")

        # Execute full application lifespan
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                # 1. Health live probe works immediately
                res_live = await client.get("/health/live")
                assert res_live.status_code == 200
                assert res_live.json()["status"] == "live"

                # 2. Health ready probe works
                res_ready = await client.get("/health/ready")
                assert res_ready.status_code in (200, 503)

        # Verify no unawaited coroutine warnings occurred
        unawaited_warnings = [
            w
            for w in recorded_warnings
            if "coroutine" in str(w.message) and "never awaited" in str(w.message)
        ]
        assert len(unawaited_warnings) == 0, (
            f"Detected unawaited coroutines: {[str(w.message) for w in unawaited_warnings]}"
        )


@pytest.mark.asyncio
async def test_redis_sync_and_async_boundaries_no_warnings():
    """Verify get_redis_client (async) and get_redis_sync (sync) never leak unawaited coroutines."""
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")

        # 1. Sync accessor called in sync context
        sync_client = get_redis_sync()
        assert sync_client is not None
        assert not hasattr(sync_client, "__await__")

        # 2. Async accessor called in async context
        async_client = await get_redis_client()
        assert async_client is not None

        # 3. BehavioralSpamDetector sync initialization
        spam_detector = BehavioralSpamDetector()
        assert spam_detector.redis_client is not None
        assert not hasattr(spam_detector.redis_client, "__await__")

        # Check recorded warnings
        unawaited_warnings = [
            w
            for w in recorded_warnings
            if "coroutine" in str(w.message) and "never awaited" in str(w.message)
        ]
        assert len(unawaited_warnings) == 0, (
            f"Detected unawaited coroutines: {[str(w.message) for w in unawaited_warnings]}"
        )


def test_production_postgresql_startup_smoke_test(monkeypatch):
    """
    Simulate production Railway environment with DATABASE_URL=postgresql://...
    Verify that:
    1. Settings normalizes it to postgresql+asyncpg://
    2. Engine created uses asyncpg dialect (no psycopg2 required)
    3. StreamIntelligenceCoordinator initializes without unawaited coroutine or psycopg2 error
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://railway_user:fake_password@containers-us-west-1.railway.app:5432/railway",
    )
    from app.core.config import get_settings
    from app.workers.intelligence import StreamIntelligenceCoordinator

    get_settings.cache_clear()
    prod_settings = get_settings()
    assert prod_settings.DATABASE_URL.startswith("postgresql+asyncpg://")

    import app.db.session as session_mod
    from app.db.session import get_engine

    # Temporarily reset global engine
    session_mod._engine = None
    session_mod._session_factory = None

    try:
        engine = get_engine()
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "asyncpg"

        # Initialize coordinator without premature database connection
        coord = StreamIntelligenceCoordinator()
        assert coord is not None
    finally:
        session_mod._engine = None
        session_mod._session_factory = None
        get_settings.cache_clear()

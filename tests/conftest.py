"""Pytest global fixtures, test database setup, and mock harnesses."""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Set testing environment before importing app
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ADMIN_SECRET"] = "test-admin-secret-12345"

import app.cache.redis as redis_module
from app.cache.redis import InMemoryRedisFallback
from app.db.base import Base
from app.db.session import get_db_session
from app.events.bus import get_event_bus
from app.main import app
from app.workers.manager import get_worker_manager
from app.youtube.quota import get_quota_manager


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a fresh in-memory SQLite database engine for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session rolled back after test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_singletons():
    """Reset singletons, in-memory caches, and worker states between tests."""
    redis_module._redis_instance = InMemoryRedisFallback()

    event_bus = get_event_bus()
    event_bus.clear()

    quota_manager = get_quota_manager()
    await quota_manager.reset_daily_quota()

    worker_manager = get_worker_manager()
    await worker_manager.stop_all()
    worker_manager.clear()

    yield

    await worker_manager.stop_all()
    worker_manager.clear()
    event_bus.clear()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP test client wired to test database session."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Secret": "test-admin-secret-12345"}

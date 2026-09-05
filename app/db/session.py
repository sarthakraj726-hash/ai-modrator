"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger("app.db.session")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the global async engine instance, creating it if needed."""
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        from app.core.database_url import normalize_database_url

        db_url = normalize_database_url(settings.DATABASE_URL, app_env=settings.APP_ENV)

        # Enable proper pooling options based on database type
        engine_kwargs = {
            "echo": False,
            "future": True,
        }
        if "sqlite" in db_url:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 20
            engine_kwargs["pool_pre_ping"] = True

        _engine = create_async_engine(db_url, **engine_kwargs)
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


def async_session_maker() -> AsyncSession:
    """Return a new AsyncSession instance from the global session factory."""
    return get_session_factory()()


async def init_db_engine() -> None:
    """Initialize database engine, run schema migrations, and ensure default records."""
    engine = get_engine()
    settings = get_settings()

    # 1. Run Alembic migrations automatically on startup
    try:
        import asyncio

        from alembic.config import Config

        from alembic import command

        def _upgrade() -> None:
            alembic_cfg = Config("alembic.ini", attributes={"configure_logger": False})
            command.upgrade(alembic_cfg, "head")

        await asyncio.to_thread(_upgrade)
        logger.info("Database schema migrations verified and up-to-date (head)")
    except Exception as mig_err:
        logger.warning(f"Alembic auto-migration warning: {mig_err}")

    # 2. Schema guarantee: Ensure all Base.metadata tables exist across all environments
    import app.db.models  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema Base.metadata verified (all tables exist)")
    except Exception as schema_err:
        logger.warning(f"Base.metadata.create_all notification: {schema_err}")

    # 3. Seed default creator if empty
    try:
        from sqlalchemy import func, select

        from app.db.models.creator import Creator

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(func.count(Creator.id))
            count_res = await session.execute(stmt)
            if (count_res.scalar() or 0) == 0:
                default_creator = Creator(
                    id="default-creator",
                    youtube_channel_id="UC_default_channel",
                    channel_name="Goddess Primary Channel",
                    enabled=True,
                )
                session.add(default_creator)
                await session.commit()
                logger.info("Seeded default primary creator record (default-creator)")
    except Exception as seed_err:
        logger.warning(f"Default creator seeding note: {seed_err}")


async def close_db_engine() -> None:
    """Dispose of the database engine pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session within a transaction context."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

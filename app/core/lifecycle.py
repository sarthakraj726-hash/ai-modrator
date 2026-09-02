"""Application lifecycle hooks: startup, dependency initialization, and graceful shutdown."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cache.redis import close_redis, init_redis
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db_engine, init_db_engine
from app.workers.manager import get_worker_manager

logger = get_logger("app.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Asynchronous context manager managing application startup and shutdown.
    Ensures all resources, pools, and workers are cleanly initialized and dismantled.
    """
    settings = get_settings()
    setup_logging(
        log_level=settings.LOG_LEVEL,
        app_env=settings.APP_ENV,
        service_name=settings.APP_NAME,
    )
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' environment")

    # 1. Initialize Database Engine
    try:
        await init_db_engine()
        logger.info("Database engine initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization warning/failure: {e}")

    # 2. Initialize Redis Connection
    try:
        await init_redis()
        logger.info("Redis client connected")
    except Exception as e:
        logger.warning(f"Redis unavailable, falling back to in-memory mode: {e}")

    # 3. Initialize Worker Manager
    worker_manager = get_worker_manager()
    logger.info("Stream worker manager initialized")

    yield

    # Shutdown Phase
    logger.info("Initiating graceful application shutdown...")

    # Stop all active stream sessions
    try:
        await worker_manager.stop_all()
        logger.info("All active stream worker sessions stopped cleanly")
    except Exception as e:
        logger.error(f"Error stopping stream workers during shutdown: {e}")

    # Close Redis client
    try:
        await close_redis()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis client: {e}")

    # Close Database Engine
    try:
        await close_db_engine()
        logger.info("Database engine pool closed")
    except Exception as e:
        logger.error(f"Error closing database engine: {e}")

    logger.info(f"{settings.APP_NAME} shutdown complete")

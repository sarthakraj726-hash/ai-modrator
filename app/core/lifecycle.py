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
    logger.info(
        f"Startup diagnostics: APP_ENV={settings.APP_ENV}, "
        f"ADMIN_SECRET={'configured' if settings.ADMIN_SECRET else 'missing'}, "
        f"DATABASE_URL={'configured' if settings.DATABASE_URL else 'missing'}, "
        f"REDIS_URL={'configured' if settings.REDIS_URL else 'missing'}, "
        f"YOUTUBE_KEYS={len(settings.youtube_api_keys)}, "
        f"AI_KEYS={'configured' if settings.OPENROUTER_API_KEY else 'missing'}"
    )

    # 1. Initialize Database Engine
    try:
        await init_db_engine()
        logger.info("Database engine initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization warning: {e}", exc_info=True)

    # 2. Initialize Redis Connection
    try:
        await init_redis()
        logger.info("Redis client connected")
    except Exception as e:
        logger.warning(f"Redis unavailable, falling back to in-memory mode: {e}")

    # 3. Initialize Distributed EventBus
    from app.events.bus import get_event_bus

    event_bus = get_event_bus()
    if not settings.is_unified_service:
        try:
            await event_bus.start_distributed_listener()
            logger.info("EventBus distributed Redis listener started")
        except Exception as e:
            logger.warning(f"Failed to start EventBus distributed listener: {e}")

    # 4. Initialize Worker Manager (Only in Worker or Unified Mode)
    worker_manager = None
    if settings.is_worker_service:
        worker_manager = get_worker_manager()
        logger.info(f"Stream worker manager initialized (mode: {settings.APP_SERVICE_MODE})")

        from app.workers.intelligence import get_intelligence_coordinator

        coordinator = get_intelligence_coordinator()
        await coordinator.start()
        logger.info("Stream intelligence coordinator initialized")
    else:
        logger.info(
            "API mode active: Stream workers bypassed to prevent duplicate worker execution"
        )

    # 5. Initialize Continuous Health Monitor Supervisor
    from app.services.health_monitor import get_health_supervisor

    health_supervisor = get_health_supervisor()
    try:
        await health_supervisor.start()
        logger.info("Continuous HealthMonitorSupervisor started")
    except Exception as e:
        logger.error(f"Failed to start HealthMonitorSupervisor: {e}")

    # 6. Initialize Monitored Channel Coordinator (Worker or Unified mode)
    monitored_coordinator = None
    if settings.is_worker_service and not settings.is_testing:
        from app.db.session import get_session_factory
        from app.services.monitored_channel_coordinator import get_monitored_channel_coordinator

        monitored_coordinator = get_monitored_channel_coordinator()
        session_factory = get_session_factory()
        await monitored_coordinator.start(session_factory)
        logger.info("MonitoredChannelCoordinator started for live stream auto-join")

    yield

    # Shutdown Phase
    logger.info("Initiating graceful application shutdown...")

    # Stop Monitored Channel Coordinator
    if monitored_coordinator:
        try:
            await monitored_coordinator.stop()
            logger.info("MonitoredChannelCoordinator stopped")
        except Exception as e:
            logger.error(f"Error stopping monitored coordinator: {e}")

    # Stop Health Monitor Supervisor
    try:
        await health_supervisor.stop()
        logger.info("HealthMonitorSupervisor stopped")
    except Exception as e:
        logger.error(f"Error stopping health supervisor: {e}")

    # Stop EventBus Distributed Listener
    try:
        await event_bus.stop_distributed_listener()
        logger.info("EventBus listener stopped")
    except Exception as e:
        logger.error(f"Error stopping EventBus listener: {e}")

    # Stop stream sessions if workers were running
    if worker_manager:
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

    # Close AI Provider client
    try:
        from app.ai.openrouter import get_ai_provider

        provider = get_ai_provider()
        if hasattr(provider, "close"):
            await provider.close()
    except Exception as e:
        logger.error(f"Error closing AI provider client: {e}")

    # Close Database Engine
    try:
        await close_db_engine()
        logger.info("Database engine pool closed")
    except Exception as e:
        logger.error(f"Error closing database engine: {e}")

    logger.info(f"{settings.APP_NAME} shutdown complete")

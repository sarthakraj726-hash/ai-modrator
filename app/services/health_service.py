"""Health check and observability diagnostic service."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.workers.manager import WorkerManager, get_worker_manager
from app.youtube.key_pool import ApiKeyPool, get_key_pool
from app.youtube.quota import QuotaManager, get_quota_manager

logger = get_logger("app.services.health")


class HealthService:
    """Provides liveness, readiness, and comprehensive health monitoring."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        worker_manager: WorkerManager | None = None,
        quota_manager: QuotaManager | None = None,
        key_pool: ApiKeyPool | None = None,
    ):
        self.session = session
        self.worker_manager = worker_manager or get_worker_manager()
        self.quota_manager = quota_manager or get_quota_manager()
        self.key_pool = key_pool or get_key_pool()

    def get_liveness(self) -> dict[str, str]:
        """Lightweight check verifying application process is responsive."""
        return {"status": "live"}

    async def get_readiness(self) -> dict[str, Any]:
        """
        Validates core external dependencies (PostgreSQL, Redis).
        Returns status 'ready' or raises/reports failure details.
        """
        db_status = "unknown"
        redis_status = "unknown"
        is_ready = True

        # 1. Check Database
        if self.session is not None:
            try:
                await self.session.execute(text("SELECT 1"))
                db_status = "healthy"
            except Exception as e:
                db_status = f"unhealthy: {str(e)}"
                is_ready = False
        else:
            db_status = "skipped (no session provided)"

        # 2. Check Redis
        try:
            redis = await get_redis_client()
            ping_ok = await redis.ping()
            redis_status = "healthy" if ping_ok else "unresponsive"
            if not ping_ok:
                is_ready = False
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
            is_ready = False

        return {
            "status": "ready" if is_ready else "degraded",
            "database": db_status,
            "redis": redis_status,
        }

    async def get_system_health(self) -> dict[str, Any]:
        """Deep diagnostic snapshot of system health, workers, and quotas."""
        readiness = await self.get_readiness()
        active_workers = await self.worker_manager.get_active_count()
        quota_used = await self.quota_manager.get_used()
        quota_remaining = await self.quota_manager.remaining()
        quota_pct = await self.quota_manager.percentage_used()
        key_status = self.key_pool.get_pool_status()
        sessions = await self.worker_manager.list_sessions()
        settings = get_settings()

        return {
            "app_name": settings.APP_NAME,
            "app_env": settings.APP_ENV,
            "status": readiness["status"],
            "dependencies": {
                "database": readiness["database"],
                "redis": readiness["redis"],
            },
            "workers": {
                "active_count": active_workers,
                "total_registered": len(sessions),
                "sessions": sessions,
            },
            "youtube": {
                "quota_daily_limit": self.quota_manager.daily_limit,
                "quota_used": quota_used,
                "quota_remaining": quota_remaining,
                "quota_percentage_used": quota_pct,
                "key_pool": key_status,
            },
        }

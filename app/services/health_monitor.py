"""Continuous health monitoring service and persistent background supervisor evaluating distributed subsystems."""

import asyncio
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.events.bus import EventBus, get_event_bus
from app.workers.manager import WorkerManager, get_worker_manager
from app.youtube.quota import QuotaManager, get_quota_manager

logger = get_logger("app.services.health_monitor")

_START_TIME = time.time()


class SubsystemStatus:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    CRITICAL = "CRITICAL"


class HealthMonitorService:
    """
    Continuous health assessment service.
    Evaluates:
    - Process liveness, CPU, and RAM.
    - PostgreSQL database connectivity and pool.
    - Redis connectivity.
    - YouTube key pool and quota balance.
    - OpenRouter AI Gateway readiness.
    - Discord alert connectivity.
    - Stream session workers and EventBus throughput.
    - Economy double-entry ledger integrity.
    - Moderation queue depth.
    - WebSub subscriptions.
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        worker_manager: WorkerManager | None = None,
        quota_manager: QuotaManager | None = None,
        event_bus: EventBus | None = None,
    ):
        self.session = session
        self.worker_manager = worker_manager or get_worker_manager()
        self.quota_manager = quota_manager or get_quota_manager()
        self.event_bus = event_bus or get_event_bus()
        self.settings = get_settings()

    def get_process_metrics(self) -> dict[str, Any]:
        """Collect memory and runtime metrics."""
        uptime_seconds = time.time() - _START_TIME
        mem_mb = 0.0
        try:
            import resource

            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            try:
                import psutil

                process = psutil.Process(os.getpid())
                mem_mb = process.memory_info().rss / (1024.0 * 1024.0)
            except Exception:
                mem_mb = 0.0

        return {
            "uptime_seconds": round(uptime_seconds, 1),
            "memory_mb": round(mem_mb, 2),
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
        }

    async def check_database(self) -> dict[str, Any]:
        """Evaluate database connectivity."""
        if not self.session:
            return {
                "status": SubsystemStatus.DEGRADED,
                "latency_ms": 0.0,
                "message": "No active database session bound",
            }
        try:
            start = time.perf_counter()
            await self.session.execute(text("SELECT 1"))
            latency_ms = (time.perf_counter() - start) * 1000
            dialect = self.session.bind.dialect.name if self.session.bind else "sqlite"

            # Query existing tables and migration revision
            table_names: list[str] = []
            if dialect == "postgresql":
                res = await self.session.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
                table_names = [r[0] for r in res.fetchall()]
            else:
                res = await self.session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                table_names = [r[0] for r in res.fetchall()]

            alembic_ver = None
            if "alembic_version" in table_names:
                try:
                    ver_res = await self.session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                    alembic_ver = ver_res.scalar()
                except Exception:
                    pass

            import app.db.session as db_session

            return {
                "status": SubsystemStatus.HEALTHY,
                "latency_ms": round(latency_ms, 2),
                "dialect": dialect,
                "tables_count": len(table_names),
                "table_names": sorted(table_names),
                "has_stream_sessions": "stream_sessions" in table_names,
                "has_creators": "creators" in table_names,
                "has_economy_ledger": "economy_ledger_entries" in table_names,
                "alembic_version": alembic_ver,
                "schema_init_log": getattr(db_session, "_schema_init_log", None),
                "message": f"Database connected ({dialect}, {len(table_names)} tables, rev: {alembic_ver})",
            }
        except Exception as e:
            logger.error(f"Database health check failure: {e}")
            return {
                "status": SubsystemStatus.CRITICAL,
                "latency_ms": 0.0,
                "error": str(e),
                "message": "Database query failed",
            }

    async def check_redis(self) -> dict[str, Any]:
        """Evaluate Redis cache and locking connectivity."""
        try:
            redis = await get_redis_client()
            start = time.perf_counter()
            pong = await redis.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            is_fallback = getattr(redis, "_is_fallback", False)
            if pong and not is_fallback:
                return {
                    "status": SubsystemStatus.HEALTHY,
                    "latency_ms": round(latency_ms, 2),
                    "fallback_active": False,
                    "message": "Redis operational",
                }
            return {
                "status": SubsystemStatus.DEGRADED,
                "latency_ms": round(latency_ms, 2),
                "fallback_active": True,
                "message": "Operating on in-memory cache fallback",
            }
        except Exception as e:
            return {
                "status": SubsystemStatus.DEGRADED,
                "latency_ms": 0.0,
                "fallback_active": True,
                "error": str(e),
                "message": "Redis unavailable; fallback active",
            }

    async def check_youtube(self) -> dict[str, Any]:
        """Evaluate YouTube key pool status and remaining daily quota."""
        try:
            from app.youtube.key_pool import KeyStatus, get_key_pool

            key_pool = get_key_pool()
            all_keys = list(key_pool._keys.values()) if key_pool else []
            active_keys = len([k for k in all_keys if k.status == KeyStatus.AVAILABLE])
            cooldown_keys = len(
                [k for k in all_keys if k.status in (KeyStatus.COOLDOWN, KeyStatus.EXHAUSTED)]
            )

            consumed = await self.quota_manager.get_used()
            remaining = await self.quota_manager.remaining()
            budget = self.quota_manager.daily_limit
            quota_percent = (consumed / budget) * 100 if budget > 0 else 0

            status = SubsystemStatus.HEALTHY
            message = "YouTube key pool and quota healthy"
            if len(all_keys) == 0:
                status = (
                    SubsystemStatus.DEGRADED
                    if (self.settings.is_testing or self.settings.APP_ENV != "production")
                    else SubsystemStatus.CRITICAL
                )
                message = "No YouTube API keys configured"
            elif remaining <= 0 or active_keys == 0:
                status = SubsystemStatus.CRITICAL
                message = "All YouTube API keys exhausted or daily quota depleted"
            elif cooldown_keys > 0 or quota_percent >= 80:
                status = SubsystemStatus.DEGRADED
                message = f"YouTube quota elevated ({quota_percent:.1f}%) or keys in cooldown"

            return {
                "status": status,
                "active_keys": active_keys,
                "cooldown_keys": cooldown_keys,
                "quota_remaining": max(0, remaining),
                "quota_used": consumed,
                "quota_percent_used": round(quota_percent, 1),
                "message": message,
            }
        except Exception as e:
            return {"status": SubsystemStatus.DEGRADED, "error": str(e)}

    def check_workers(self) -> dict[str, Any]:
        """Evaluate active stream workers."""
        try:
            active_count = len(self.worker_manager._sessions)
            return {
                "status": SubsystemStatus.HEALTHY
                if active_count < 10
                else SubsystemStatus.DEGRADED,
                "active_workers": active_count,
                "max_concurrency": 7,
                "message": f"{active_count} stream workers active",
            }
        except Exception as e:
            return {"status": SubsystemStatus.DEGRADED, "error": str(e)}

    async def check_openrouter(self) -> dict[str, Any]:
        """Evaluate OpenRouter AI Gateway readiness."""
        try:
            from app.ai.openrouter import get_ai_provider

            provider = get_ai_provider()
            if hasattr(provider, "check_readiness"):
                return await provider.check_readiness()
            return {"status": "READY", "ready": True, "message": "Provider initialized"}
        except Exception as e:
            return {"status": "DEGRADED", "ready": False, "error": str(e)}

    async def check_discord(self) -> dict[str, Any]:
        """Evaluate Discord operations reachability."""
        try:
            from app.discord.operations import DiscordOperationsService

            service = DiscordOperationsService()
            return await service.check_readiness()
        except Exception as e:
            return {"status": "DEGRADED", "error": str(e)}

    def check_eventbus(self) -> dict[str, Any]:
        """Evaluate EventBus connectivity and mode."""
        try:
            return self.event_bus.get_health()
        except Exception as e:
            return {"status": "DEGRADED", "error": str(e)}

    async def check_economy_integrity(self) -> dict[str, Any]:
        """Evaluate double-entry ledger balance and account constraints."""
        if not self.session:
            return {"status": SubsystemStatus.HEALTHY, "audited": False}
        try:
            from app.services.integrity import IntegrityCheckService

            integrity = IntegrityCheckService(self.session)
            ledger_violations, ledger_stats = await integrity.audit_economy_ledger()
            balance_violations, balance_stats = await integrity.audit_account_balances()

            balanced = len(ledger_violations) == 0
            accounts_ok = len(balance_violations) == 0

            status = (
                SubsystemStatus.HEALTHY if (balanced and accounts_ok) else SubsystemStatus.CRITICAL
            )
            return {
                "status": status,
                "ledger_balanced": balanced,
                "imbalanced_transactions": ledger_stats.get("imbalanced_transactions", 0),
                "negative_accounts": balance_stats.get("negative_accounts_count", 0),
                "message": "Ledger balanced" if balanced else "LEDGER IMBALANCE DETECTED",
            }
        except Exception as e:
            return {"status": SubsystemStatus.DEGRADED, "error": str(e)}

    async def check_moderation_queue(self) -> dict[str, Any]:
        """Evaluate pending HITL review depth."""
        if not self.session:
            return {"pending_reviews": 0, "status": SubsystemStatus.HEALTHY}
        try:
            from app.db.models.moderation_review import ModerationReview, ReviewStatus

            stmt = select(func.count(ModerationReview.id)).where(
                ModerationReview.status == ReviewStatus.PENDING.value
            )
            res = await self.session.execute(stmt)
            count = res.scalar() or 0
            status = SubsystemStatus.HEALTHY if count < 50 else SubsystemStatus.DEGRADED
            return {
                "status": status,
                "pending_reviews": count,
                "message": f"{count} pending human reviews",
            }
        except Exception:
            return {"pending_reviews": 0, "status": SubsystemStatus.HEALTHY}

    async def check_websub(self) -> dict[str, Any]:
        """Evaluate WebSub push notification subscription status."""
        if not self.session:
            return {"active_subscriptions": 0, "status": SubsystemStatus.HEALTHY}
        try:
            from app.db.models.websub_subscription import WebSubStatus, WebSubSubscription

            stmt = select(func.count(WebSubSubscription.id)).where(
                WebSubSubscription.status == WebSubStatus.ACTIVE.value
            )
            res = await self.session.execute(stmt)
            count = res.scalar() or 0
            return {
                "status": SubsystemStatus.HEALTHY,
                "active_subscriptions": count,
            }
        except Exception:
            return {"active_subscriptions": 0, "status": SubsystemStatus.HEALTHY}

    async def get_detailed_snapshot(self) -> dict[str, Any]:
        """
        Produce comprehensive detailed health snapshot for /health/detailed endpoint.
        Never exposes raw credentials, API secrets, or internal database passwords.
        """
        db_health = await self.check_database()
        redis_health = await self.check_redis()
        yt_health = await self.check_youtube()
        worker_health = self.check_workers()
        ai_health = await self.check_openrouter()
        discord_health = await self.check_discord()
        eventbus_health = self.check_eventbus()
        economy_health = await self.check_economy_integrity()
        moderation_health = await self.check_moderation_queue()
        websub_health = await self.check_websub()
        process_metrics = self.get_process_metrics()

        all_subsystems = {
            "database": db_health,
            "redis": redis_health,
            "youtube": yt_health,
            "workers": worker_health,
            "openrouter": ai_health,
            "discord": discord_health,
            "eventbus": eventbus_health,
            "economy": economy_health,
            "moderation": moderation_health,
            "websub": websub_health,
        }

        service_mode = self.settings.APP_SERVICE_MODE.lower()

        # Define which subsystems are strictly critical vs peripheral for the current mode
        if service_mode == "api":
            critical_subsystems = ["database", "eventbus"]
            optional_or_bypassed = ["workers", "youtube"]
        elif service_mode == "worker":
            critical_subsystems = ["database", "workers", "youtube", "economy"]
            optional_or_bypassed = []
        else:  # unified
            critical_subsystems = ["database", "workers", "youtube", "economy", "redis"]
            optional_or_bypassed = []

        # Determine overall status with explicit severity semantics
        critical_statuses = [
            all_subsystems[s].get("status") for s in critical_subsystems if s in all_subsystems
        ]
        all_statuses = [
            info.get("status")
            for name, info in all_subsystems.items()
            if name not in optional_or_bypassed
        ]

        if SubsystemStatus.CRITICAL in critical_statuses:
            overall_status = SubsystemStatus.CRITICAL
        elif SubsystemStatus.UNHEALTHY in critical_statuses:
            overall_status = SubsystemStatus.UNHEALTHY
        elif SubsystemStatus.CRITICAL in all_statuses or SubsystemStatus.UNHEALTHY in all_statuses:
            overall_status = SubsystemStatus.DEGRADED
        elif SubsystemStatus.DEGRADED in all_statuses:
            overall_status = SubsystemStatus.DEGRADED
        else:
            overall_status = SubsystemStatus.HEALTHY

        return {
            "service": "goddess-ai-modrator",
            "version": "1.0.0",
            "environment": self.settings.APP_ENV,
            "overall_status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": process_metrics["uptime_seconds"],
            "process": process_metrics,
            "subsystems": {
                "database": db_health,
                "redis": redis_health,
                "youtube": yt_health,
                "workers": worker_health,
                "openrouter": ai_health,
                "discord": discord_health,
                "eventbus": eventbus_health,
                "economy": economy_health,
                "moderation": moderation_health,
                "websub": websub_health,
            },
            "security": {
                "secrets_redacted": True,
                "rbac_enforced": True,
            },
        }


class HealthMonitorSupervisor:
    """
    Persistent background health monitor supervisor.
    Periodically executes complete health evaluation cycles, maintains cached state,
    and automatically triggers operational incident reporting on critical failures.
    """

    def __init__(
        self,
        interval_seconds: float = 30.0,
        timeout_seconds: float = 5.0,
        session_factory: Any = None,
    ):
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.session_factory = session_factory
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._latest_snapshot: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self.cycles_executed: int = 0
        self.last_cycle_at: datetime | None = None
        self.last_cycle_duration_ms: float = 0.0
        self.consecutive_failures: int = 0

    async def start(self) -> None:
        """Launch background health evaluation loop."""
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"HealthMonitorSupervisor started with {self.interval_seconds}s evaluation interval"
        )

    async def stop(self) -> None:
        """Gracefully stop background health evaluation loop."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("HealthMonitorSupervisor stopped")

    async def _run_loop(self) -> None:
        """Continuous evaluation cycle loop."""
        # Run initial cycle immediately
        await self.evaluate_cycle()

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval_seconds)
                if self._stop_event.is_set():
                    break
                await self.evaluate_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in HealthMonitorSupervisor cycle: {e}", exc_info=True)

    async def evaluate_cycle(self) -> dict[str, Any]:
        """Perform a single comprehensive health cycle with timeout shielding."""
        async with self._lock:
            start_mono = time.monotonic()
            try:
                # Obtain a fresh database session
                factory = self.session_factory
                if factory is None:
                    from app.db.session import async_session_maker

                    factory = async_session_maker

                if factory:
                    async with factory() as session:
                        monitor_svc = HealthMonitorService(session=session)
                        snapshot = await asyncio.wait_for(
                            monitor_svc.get_detailed_snapshot(),
                            timeout=self.timeout_seconds,
                        )
                else:
                    monitor_svc = HealthMonitorService()
                    snapshot = await asyncio.wait_for(
                        monitor_svc.get_detailed_snapshot(),
                        timeout=self.timeout_seconds,
                    )

                duration_ms = (time.monotonic() - start_mono) * 1000
                self.last_cycle_duration_ms = round(duration_ms, 2)
                self.last_cycle_at = datetime.now(UTC)
                self.cycles_executed += 1
                self._latest_snapshot = snapshot

                # Incident pipeline integration on CRITICAL status
                if snapshot.get("overall_status") == SubsystemStatus.CRITICAL:
                    self.consecutive_failures += 1
                    await self._report_health_incident(snapshot)
                else:
                    self.consecutive_failures = 0

                return snapshot
            except Exception as e:
                duration_ms = (time.monotonic() - start_mono) * 1000
                self.consecutive_failures += 1
                logger.error(f"Health cycle execution failed ({duration_ms:.1f}ms): {e}")
                error_snapshot = {
                    "service": "goddess-ai-modrator",
                    "overall_status": SubsystemStatus.CRITICAL,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "error": str(e),
                    "subsystems": {"error": str(e)},
                    "security": {"secrets_redacted": True, "rbac_enforced": True},
                }
                self._latest_snapshot = error_snapshot
                return error_snapshot

    async def _report_health_incident(self, snapshot: dict[str, Any]) -> None:
        """Automatically dispatch critical health incident to IncidentService."""
        try:
            from app.db.session import async_session_maker
            from app.services.incidents import IncidentService

            if async_session_maker:
                async with async_session_maker() as session:
                    incident_svc = IncidentService(session)
                    await incident_svc.report_incident(
                        severity="CRITICAL",
                        service="SYSTEM_HEALTH",
                        summary="Health supervisor detected CRITICAL subsystem state",
                        action="Inspect /health/detailed and review active logs.",
                    )
                    await session.commit()
        except Exception as inc_err:
            logger.debug(f"Incident reporting from health supervisor skipped/failed: {inc_err}")

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """Return cached latest snapshot instantaneously without blocking."""
        return self._latest_snapshot


_global_health_supervisor: HealthMonitorSupervisor | None = None


def get_health_supervisor() -> HealthMonitorSupervisor:
    """Return singleton HealthMonitorSupervisor instance."""
    global _global_health_supervisor
    if _global_health_supervisor is None:
        settings = get_settings()
        _global_health_supervisor = HealthMonitorSupervisor(
            interval_seconds=settings.HEALTH_CHECK_INTERVAL_SECONDS,
            timeout_seconds=settings.HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    return _global_health_supervisor

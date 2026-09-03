from typing import Any

from fastapi import APIRouter, Response, status

from app.api.dependencies import DBSessionDep, HealthServiceDep
from app.api.schemas.health import (
    LivenessResponse,
    ReadinessResponse,
    SystemHealthResponse,
)

router = APIRouter(prefix="/health", tags=["Health & Observability"])


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness Probe",
    description="Extremely lightweight check verifying application process responsiveness.",
)
async def get_live(service: HealthServiceDep) -> LivenessResponse:
    return LivenessResponse(**service.get_liveness())


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness Probe",
    description="Validates external dependencies with mode-dependent readiness semantics.",
)
async def get_ready(service: HealthServiceDep, response: Response) -> ReadinessResponse:
    from app.core.config import get_settings

    settings = get_settings()
    readiness = await service.get_readiness()

    # In worker or unified mode, check that worker manager is operational
    if settings.is_worker_service:
        from app.workers.manager import get_worker_manager

        worker_mgr = get_worker_manager()
        if not hasattr(worker_mgr, "_sessions"):
            readiness["status"] = "degraded"
            readiness["details"]["workers"] = "uninitialized"

    if readiness["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(**readiness)


@router.get(
    "",
    response_model=SystemHealthResponse,
    summary="System Health & Metrics Overview",
    description="Returns detailed diagnostics regarding database, Redis, workers, and YouTube quota consumption.",
)
async def get_system_health(service: HealthServiceDep) -> SystemHealthResponse:
    health_data = await service.get_system_health()
    return SystemHealthResponse(**health_data)


@router.get(
    "/detailed",
    summary="Detailed Subsystem Health & Diagnostics",
    description="Returns continuous monitoring telemetry across all subsystems without exposing secrets.",
)
async def get_detailed_health(db: DBSessionDep) -> dict[str, Any]:
    from app.services.health_monitor import HealthMonitorService, get_health_supervisor

    supervisor = get_health_supervisor()
    cached = supervisor.get_latest_snapshot()
    if cached:
        return cached

    # Fall back to on-demand snapshot if supervisor hasn't completed first cycle
    monitor = HealthMonitorService(session=db)
    return await monitor.get_detailed_snapshot()

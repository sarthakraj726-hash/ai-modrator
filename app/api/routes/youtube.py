"""Developer endpoints for YouTube Engine status, quota diagnostics, and key pool health."""

from fastapi import APIRouter, Depends

from app.api.schemas.youtube import (
    YouTubeDiscoveryStatusResponse,
    YouTubeKeysResponse,
    YouTubeQuotaResponse,
    YouTubeStatusResponse,
)
from app.core.security import verify_admin_secret
from app.workers.manager import get_worker_manager
from app.youtube.discovery import get_discovery_scheduler
from app.youtube.key_pool import KeyStatus, get_key_pool
from app.youtube.quota import get_quota_manager

router = APIRouter(prefix="/youtube", tags=["YouTube Engine"])


@router.get(
    "/status", response_model=YouTubeStatusResponse, dependencies=[Depends(verify_admin_secret)]
)
async def get_youtube_status() -> YouTubeStatusResponse:
    """Return high-level operational status of YouTube subsystem."""
    quota_mgr = get_quota_manager()
    key_pool = get_key_pool()
    worker_mgr = get_worker_manager()
    discovery = get_discovery_scheduler()

    rem = await quota_mgr.remaining()
    pct = await quota_mgr.percentage_used()
    pool_stats = key_pool.get_pool_status()
    available_keys = len([k for k in pool_stats if k["status"] == KeyStatus.AVAILABLE.value])

    return YouTubeStatusResponse(
        status="operational",
        daily_budget=quota_mgr.daily_limit,
        remaining_quota=rem,
        percentage_quota_used=pct,
        key_pool_total=len(pool_stats),
        key_pool_available=available_keys,
        discovery_active=discovery.get_status()["running"],
        active_stream_sessions=await worker_mgr.get_active_count(),
    )


@router.get(
    "/quota", response_model=YouTubeQuotaResponse, dependencies=[Depends(verify_admin_secret)]
)
async def get_youtube_quota() -> YouTubeQuotaResponse:
    """Return detailed YouTube Data API quota diagnostics and per-method breakdown."""
    quota_mgr = get_quota_manager()
    metrics = await quota_mgr.get_metrics()
    return YouTubeQuotaResponse(**metrics)


@router.get(
    "/keys", response_model=YouTubeKeysResponse, dependencies=[Depends(verify_admin_secret)]
)
async def get_youtube_keys() -> YouTubeKeysResponse:
    """Return health, cooldown status, and metrics for all API keys in pool."""
    key_pool = get_key_pool()
    pool_stats = key_pool.get_pool_status()

    available = len([k for k in pool_stats if k["status"] == KeyStatus.AVAILABLE.value])
    cooldown = len([k for k in pool_stats if k["status"] == KeyStatus.COOLDOWN.value])
    exhausted = len([k for k in pool_stats if k["status"] == KeyStatus.EXHAUSTED.value])
    invalid = len([k for k in pool_stats if k["status"] == KeyStatus.INVALID.value])

    return YouTubeKeysResponse(
        total_keys=len(pool_stats),
        available_keys=available,
        cooldown_keys=cooldown,
        exhausted_keys=exhausted,
        invalid_keys=invalid,
        keys=pool_stats,
    )


@router.get(
    "/discovery/status",
    response_model=YouTubeDiscoveryStatusResponse,
    dependencies=[Depends(verify_admin_secret)],
)
async def get_discovery_status() -> YouTubeDiscoveryStatusResponse:
    """Return status and metrics of YouTube Discovery Scheduler."""
    discovery = get_discovery_scheduler()
    return YouTubeDiscoveryStatusResponse(**discovery.get_status())

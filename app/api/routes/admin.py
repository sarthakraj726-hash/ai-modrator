"""Admin diagnostic and audit API routes."""

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import AdminUserDep, DBSessionDep
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.system_event_repo import SystemEventRepository
from app.youtube.key_pool import get_key_pool
from app.youtube.quota import get_quota_manager

router = APIRouter(prefix="/admin", tags=["Admin & Diagnostics"])


@router.get("/key-pool", summary="Get YouTube API Key Pool health and diagnostics")
async def get_key_pool_status(admin: AdminUserDep) -> list[dict[str, Any]]:
    key_pool = get_key_pool()
    return key_pool.get_pool_status()


@router.get("/quota", summary="Get YouTube quota consumption metrics")
async def get_quota_status(admin: AdminUserDep) -> dict[str, Any]:
    qm = get_quota_manager()
    used = await qm.get_used()
    rem = await qm.remaining()
    pct = await qm.percentage_used()
    return {
        "daily_limit": qm.daily_limit,
        "used": used,
        "remaining": rem,
        "percentage_used": pct,
    }


@router.get("/audits/stream/{session_id}", summary="Get audit trail for a stream session")
async def get_stream_audits(
    session_id: str,
    session: DBSessionDep,
    admin: AdminUserDep,
    limit: int = 50,
) -> list[dict[str, Any]]:
    audit_repo = AuditRepository(session)
    events = await audit_repo.list_by_stream(session_id, limit=limit)
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "creator_id": e.creator_id,
            "stream_session_id": e.stream_session_id,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/system-events", summary="Get recent system warning and error events")
async def get_recent_system_events(
    session: DBSessionDep,
    admin: AdminUserDep,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sys_repo = SystemEventRepository(session)
    events = await sys_repo.list_recent(limit=limit)
    return [
        {
            "id": e.id,
            "severity": e.severity,
            "event_type": e.event_type,
            "service": e.service,
            "stream_session_id": e.stream_session_id,
            "message": e.message,
            "metadata": e.metadata_payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]

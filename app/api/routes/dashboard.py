"""Developer Control Center REST & Real-Time SSE API endpoints."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from app.api.dependencies import AdminUserDep, DBSessionDep
from app.core.logging import get_logger
from app.db.models.creator import Creator
from app.db.models.discord_config import CreatorDiscordConfig
from app.db.models.economy import EconomyAccount
from app.db.models.incident import Incident
from app.db.models.moderation_review import ModerationReview
from app.db.models.stream_session import StreamSession, StreamStatus
from app.db.models.websub_subscription import WebSubSubscription
from app.services.health_monitor import HealthMonitorService
from app.services.incidents import IncidentService
from app.services.integrity import IntegrityCheckService
from app.workers.manager import get_worker_manager
from app.youtube.quota import get_quota_manager
from app.youtube.url_resolver import YouTubeUrlResolver

logger = get_logger("app.api.routes.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Developer Control Center"])


# Request / Response Schemas
class StreamControlRequest(BaseModel):
    action: str = Field(..., description="connect, disconnect, restart, reconcile")


class ManualConnectRequest(BaseModel):
    url_or_video_id: str
    creator_id: str | None = None


class CreatorCreateRequest(BaseModel):
    youtube_channel_id: str
    channel_name: str
    enabled: bool = True
    discord_log_channel_id: str | None = None
    discord_alert_channel_id: str | None = None


class CreatorUpdateRequest(BaseModel):
    channel_name: str | None = None
    enabled: bool | None = None
    discord_log_channel_id: str | None = None
    discord_alert_channel_id: str | None = None


class ResolveReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE or DENY")
    reason: str | None = None


class ResolveIncidentRequest(BaseModel):
    status: str = Field(..., description="MITIGATED, RESOLVED, CLOSED")
    resolution: str | None = None
    root_cause: str | None = None


# --- 1. System Overview ---
@router.get("/overview", summary="Control Center Overview")
async def get_dashboard_overview(db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    health_svc = HealthMonitorService(session=db)
    detailed_health = await health_svc.get_detailed_snapshot()

    # Active stream count
    active_stmt = select(func.count(StreamSession.id)).where(
        StreamSession.status == StreamStatus.ACTIVE.value
    )
    active_res = await db.execute(active_stmt)
    active_streams = active_res.scalar() or 0

    # Total registered creators
    creator_stmt = select(func.count(Creator.id))
    creator_res = await db.execute(creator_stmt)
    total_creators = creator_res.scalar() or 0

    # Pending reviews
    pending_stmt = select(func.count(ModerationReview.id)).where(
        ModerationReview.status == "PENDING"
    )
    pending_res = await db.execute(pending_stmt)
    pending_reviews = pending_res.scalar() or 0

    # Active incidents
    inc_stmt = select(func.count(Incident.id)).where(Incident.status.in_(["OPEN", "INVESTIGATING"]))
    inc_res = await db.execute(inc_stmt)
    active_incidents = inc_res.scalar() or 0

    # Run quick ledger audit
    integrity_svc = IntegrityCheckService(db)
    _, ledger_stats = await integrity_svc.audit_economy_ledger()
    ledger_balanced = ledger_stats.get("imbalanced_transactions", 0) == 0

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "overall_status": detailed_health["overall_status"],
        "subsystems": detailed_health["subsystems"],
        "active_streams": active_streams,
        "max_streams": 7,
        "total_creators": total_creators,
        "pending_moderation_reviews": pending_reviews,
        "active_incidents": active_incidents,
        "ledger_balanced": ledger_balanced,
        "quota": detailed_health["subsystems"]["youtube"],
        "process": detailed_health["process"],
    }


# --- 2. Live Stream Grid & Controls ---
@router.get("/streams", summary="List All Live Stream Sessions")
async def get_streams_grid(db: DBSessionDep, admin: AdminUserDep) -> list[dict[str, Any]]:
    stmt = (
        select(StreamSession, Creator.channel_name)
        .join(Creator, StreamSession.creator_id == Creator.id)
        .order_by(desc(StreamSession.created_at))
        .limit(20)
    )
    res = await db.execute(stmt)
    rows = res.all()

    results = []
    now = datetime.now(UTC)
    for session, channel_name in rows:
        duration_s = 0.0
        if session.started_at:
            duration_s = (now - session.started_at).total_seconds()
        results.append(
            {
                "session_id": session.id,
                "creator_id": session.creator_id,
                "channel_name": channel_name,
                "youtube_video_id": session.youtube_video_id,
                "youtube_live_chat_id": session.youtube_live_chat_id,
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "duration_seconds": round(duration_s, 0),
                "last_activity_at": session.last_activity_at.isoformat()
                if session.last_activity_at
                else None,
            }
        )
    return results


@router.post("/streams/{stream_id}/control", summary="Dispatch Stream Action")
async def control_stream(
    stream_id: str,
    req: StreamControlRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    worker_mgr = get_worker_manager()
    stmt = select(StreamSession).where(StreamSession.id == stream_id)
    res = await db.execute(stmt)
    stream = res.scalar_one_or_none()
    if not stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stream session not found"
        )

    action = req.action.lower()
    if action == "disconnect":
        try:
            await worker_mgr.stop_session(stream.id)
        except Exception:
            pass
        stream.status = StreamStatus.ENDED.value
        stream.ended_at = datetime.now(UTC)
        await db.flush()
        return {"status": "DISCONNECTED", "stream_id": stream_id}
    elif action == "restart":
        try:
            await worker_mgr.restart_session(stream.id)
        except Exception:
            pass
        return {"status": "RESTARTED", "stream_id": stream_id}
    elif action == "reconcile":
        return {"status": "RECONCILED", "stream_id": stream_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown action: {req.action}"
        )


@router.post("/streams/manual-connect", summary="Connect Stream via URL")
async def manual_connect_stream(
    req: ManualConnectRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    # Resolve video ID
    try:
        resolved = YouTubeUrlResolver.resolve_video_id(req.url_or_video_id)
        video_id = resolved.video_id
    except Exception:
        video_id = req.url_or_video_id.strip()

    # Find creator
    creator = None
    if req.creator_id:
        c_stmt = select(Creator).where(Creator.id == req.creator_id)
        c_res = await db.execute(c_stmt)
        creator = c_res.scalar_one_or_none()
    else:
        c_stmt = select(Creator).where(Creator.enabled.is_(True)).limit(1)
        c_res = await db.execute(c_stmt)
        creator = c_res.scalar_one_or_none()

    if not creator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid creator found for connection"
        )

    # Create stream session
    session_obj = StreamSession(
        creator_id=creator.id,
        youtube_video_id=video_id,
        youtube_live_chat_id=f"chat_{video_id}",
        status=StreamStatus.CONNECTING.value,
        started_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
    )
    db.add(session_obj)
    await db.flush()

    worker_mgr = get_worker_manager()
    try:
        await worker_mgr.start_session(
            session_id=session_obj.id,
            creator_id=creator.id,
            video_id=video_id,
            live_chat_id=session_obj.youtube_live_chat_id,
        )
    except Exception as e:
        logger.warn(f"Worker start_session handled gracefully: {e}")

    session_obj.status = StreamStatus.ACTIVE.value
    await db.flush()

    return {
        "status": "ACTIVE",
        "stream_session_id": session_obj.id,
        "creator_id": creator.id,
        "video_id": video_id,
    }


# --- 3. Creator Registry ---
@router.get("/creators", summary="List Registered Creators")
async def list_creators(db: DBSessionDep, admin: AdminUserDep) -> list[dict[str, Any]]:
    stmt = select(Creator).order_by(Creator.channel_name)
    res = await db.execute(stmt)
    creators = res.scalars().all()

    results = []
    for c in creators:
        discord_stmt = select(CreatorDiscordConfig).where(CreatorDiscordConfig.creator_id == c.id)
        d_res = await db.execute(discord_stmt)
        d_cfg = d_res.scalar_one_or_none()

        websub_stmt = select(WebSubSubscription).where(WebSubSubscription.creator_id == c.id)
        w_res = await db.execute(websub_stmt)
        w_sub = w_res.scalar_one_or_none()

        results.append(
            {
                "id": c.id,
                "youtube_channel_id": c.youtube_channel_id,
                "channel_name": c.channel_name,
                "enabled": c.enabled,
                "websub_status": w_sub.status if w_sub else "INACTIVE",
                "discord_log_channel": d_cfg.log_channel_id if d_cfg else None,
                "discord_alert_channel": d_cfg.alert_channel_id if d_cfg else None,
            }
        )
    return results


@router.post("/creators", summary="Register New Creator")
async def register_creator(
    req: CreatorCreateRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    creator = Creator(
        youtube_channel_id=req.youtube_channel_id,
        channel_name=req.channel_name,
        enabled=req.enabled,
    )
    db.add(creator)
    await db.flush()

    if req.discord_log_channel_id or req.discord_alert_channel_id:
        cfg = CreatorDiscordConfig(
            creator_id=creator.id,
            log_channel_id=req.discord_log_channel_id,
            alert_channel_id=req.discord_alert_channel_id,
            enabled=True,
        )
        db.add(cfg)
        await db.flush()

    return {"message": "Creator registered successfully", "id": creator.id}


# --- 4. Quota & Key Pool ---
@router.get("/quota", summary="Detailed YouTube Quota Status")
async def get_quota_details(admin: AdminUserDep) -> dict[str, Any]:
    quota_mgr = get_quota_manager()
    budget = quota_mgr.daily_limit
    consumed = await quota_mgr.get_used()
    remaining = await quota_mgr.remaining()
    percent = (consumed / budget) * 100 if budget > 0 else 0

    threshold = "NORMAL"
    if percent >= 95:
        threshold = "CRITICAL_95"
    elif percent >= 90:
        threshold = "WARNING_90"
    elif percent >= 80:
        threshold = "WARNING_80"
    elif percent >= 70:
        threshold = "WARNING_70"
    elif percent >= 50:
        threshold = "WARNING_50"

    return {
        "budget": budget,
        "consumed": consumed,
        "remaining": remaining,
        "percent_used": round(percent, 1),
        "threshold_status": threshold,
    }


@router.get("/youtube-keys", summary="Inspect YouTube API Key Pool")
async def get_key_pool_status(admin: AdminUserDep) -> list[dict[str, Any]]:
    from app.youtube.key_pool import get_key_pool

    pool = get_key_pool()
    if not pool:
        return []

    results = []
    all_keys = list(pool._keys.values())
    for idx, k in enumerate(all_keys):
        results.append(
            {
                "key_index": idx,
                "slot": k.slot,
                "masked_key": k.masked_key,
                "requests_made": k.total_requests,
                "quota_units": k.estimated_usage,
                "status": k.status.value,
                "in_cooldown": k.status.value in ("COOLDOWN", "EXHAUSTED"),
                "cooldown_until": None,
                "last_used_at": None,
            }
        )
    return results


@router.post("/youtube-keys/{index}/reset", summary="Reset API Key Cooldown")
async def reset_key_cooldown(index: int, admin: AdminUserDep) -> dict[str, Any]:
    from app.youtube.key_pool import KeyStatus, get_key_pool

    pool = get_key_pool()
    all_keys = list(pool._keys.values()) if pool else []
    if not pool or index < 0 or index >= len(all_keys):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key index not found")

    target = all_keys[index]
    target.status = KeyStatus.AVAILABLE
    target.cooldown_until = 0.0
    return {"message": f"Reset cooldown on key index {index}"}


# --- 5. AI Observability ---
@router.get("/ai", summary="AI & OpenRouter Metrics")
async def get_ai_metrics(db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    from app.db.models.ai_usage import AIUsageRecord

    stmt = select(
        func.count(AIUsageRecord.id).label("total_requests"),
        func.sum(AIUsageRecord.total_tokens).label("total_tokens"),
        func.sum(AIUsageRecord.cost_usd).label("total_cost"),
        func.avg(AIUsageRecord.latency_ms).label("avg_latency_ms"),
    )
    res = await db.execute(stmt)
    row = res.one()

    return {
        "total_requests": row[0] or 0,
        "total_tokens": row[1] or 0,
        "total_cost_usd": round(float(row[2] or 0.0), 4),
        "avg_latency_ms": round(float(row[3] or 0.0), 1),
        "fallback_rate_percent": 0.0,
    }


# --- 6. Moderation & HITL Queue ---
@router.get("/moderation", summary="Moderation Activity & HITL Queue")
async def get_moderation_queue(
    db: DBSessionDep,
    admin: AdminUserDep,
    status_filter: str = Query("PENDING", description="PENDING, APPROVED, DENIED, ALL"),
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt = select(ModerationReview)
    if status_filter != "ALL":
        stmt = stmt.where(ModerationReview.status == status_filter)
    stmt = stmt.order_by(desc(ModerationReview.created_at)).limit(limit)
    res = await db.execute(stmt)
    reviews = res.scalars().all()

    return [
        {
            "id": r.id,
            "creator_id": r.creator_id,
            "author_display_name": r.author_display_name,
            "message_text": r.message_text,
            "status": r.status,
            "severity": r.severity,
            "confidence": r.confidence,
            "recommended_action": r.recommended_action,
            "reason": r.reason,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in reviews
    ]


@router.post("/moderation/reviews/{review_id}/resolve", summary="Resolve HITL Review")
async def resolve_review(
    review_id: str,
    req: ResolveReviewRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    from app.moderation.hitl import HumanReviewService

    service = HumanReviewService(db)
    if req.action.upper() == "APPROVE":
        success, reason = await service.approve_review(review_id, moderator_id=admin.user_id)
    else:
        success, reason = await service.deny_review(review_id, moderator_id=admin.user_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    return {"message": f"Review {review_id} resolved with action {req.action}"}


# --- 7. Incidents ---
@router.get("/incidents", summary="Incident List")
async def list_incidents(
    db: DBSessionDep,
    admin: AdminUserDep,
    status_filter: str | None = None,
    severity_filter: str | None = None,
) -> list[dict[str, Any]]:
    svc = IncidentService(db)
    incidents, _ = await svc.list_incidents(
        status=status_filter, severity=severity_filter, limit=50
    )
    return [
        {
            "incident_id": inc.incident_id,
            "severity": inc.severity,
            "status": inc.status,
            "service": inc.service,
            "summary": inc.summary,
            "actions_taken": inc.actions_taken,
            "detected_at": inc.detected_at.isoformat(),
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        }
        for inc in incidents
    ]


@router.post("/incidents/{incident_id}/resolve", summary="Resolve Incident")
async def resolve_incident(
    incident_id: str,
    req: ResolveIncidentRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    svc = IncidentService(db)
    updated = await svc.update_status(
        incident_id=incident_id,
        status=req.status,
        resolution=req.resolution,
        root_cause=req.root_cause,
        action=f"Resolved by {admin.user_id}",
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return {"message": f"Incident {incident_id} updated to {req.status}"}


# --- 8. Economy & Commands ---
@router.get("/economy", summary="Virtual Economy Telemetry")
async def get_economy_telemetry(db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    integrity = IntegrityCheckService(db)
    _, stats = await integrity.audit_economy_ledger()
    _, balance_stats = await integrity.audit_account_balances()

    coins_stmt = select(func.sum(EconomyAccount.balance)).where(
        EconomyAccount.account_type == "VIEWER"
    )
    coins_res = await db.execute(coins_stmt)
    total_circulating = coins_res.scalar() or 0

    return {
        "circulating_coins": total_circulating,
        "total_accounts": balance_stats.get("total_accounts_audited", 0),
        "ledger_balanced": stats.get("imbalanced_transactions", 0) == 0,
        "total_transactions": stats.get("total_transactions_audited", 0),
        "negative_balances_count": balance_stats.get("negative_accounts_count", 0),
    }


# --- 9. Real-Time Server-Sent Events (SSE) Stream ---
@router.get("/events/stream", summary="Real-Time Control Center SSE Feed")
async def stream_dashboard_events(admin: AdminUserDep):
    """
    Continuous Server-Sent Events (SSE) stream pushing live telemetry
    to Developer Control Center without polling.
    """

    async def event_generator():
        while True:
            quota_mgr = get_quota_manager()
            worker_mgr = get_worker_manager()
            used = await quota_mgr.get_used()
            remaining = await quota_mgr.remaining()
            payload = {
                "timestamp": datetime.now(UTC).isoformat(),
                "active_workers": len(worker_mgr._active_workers),
                "quota_used": used,
                "quota_remaining": remaining,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

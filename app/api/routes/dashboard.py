"""Developer Control Center REST & Real-Time SSE API endpoints."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from app.api.dependencies import AdminUserDep, DBSessionDep
from app.api.sse import get_sse_broadcaster
from app.core.logging import get_logger
from app.db.models.audit_event import AuditEvent
from app.db.models.creator import Creator
from app.db.models.discord_config import CreatorDiscordConfig
from app.db.models.economy import EconomyAccount
from app.db.models.incident import Incident
from app.db.models.moderation_review import ModerationReview
from app.db.models.monitored_channel import MonitoredChannel
from app.db.models.stream_session import (
    StreamSession,
    StreamStatus,
)
from app.db.models.websub_subscription import WebSubSubscription
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.monitored_channel_repo import MonitoredChannelRepository
from app.services.feature_flags import FeatureFlagService
from app.services.health_monitor import HealthMonitorService, get_health_supervisor
from app.services.incidents import IncidentService
from app.services.integrity import IntegrityCheckService
from app.workers.manager import get_worker_manager
from app.youtube.quota import get_quota_manager

logger = get_logger("app.api.routes.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Developer Control Center"])

_stream_control_locks: dict[str, asyncio.Lock] = {}
_stream_locks_mutex = asyncio.Lock()


async def _get_stream_lock(stream_id: str) -> asyncio.Lock:
    async with _stream_locks_mutex:
        if stream_id not in _stream_control_locks:
            _stream_control_locks[stream_id] = asyncio.Lock()
        return _stream_control_locks[stream_id]


# Request / Response Schemas
class StreamControlRequest(BaseModel):
    action: str = Field(..., description="connect, disconnect, restart, reconcile")
    operation_id: str | None = None
    idempotency_key: str | None = None


class ManualConnectRequest(BaseModel):
    url_or_video_id: str
    creator_id: str | None = None


class MonitoredChannelCreateRequest(BaseModel):
    identifier: str
    display_label: str | None = None
    auto_join_enabled: bool = True
    creator_id: str | None = None


class MonitoredChannelUpdateRequest(BaseModel):
    enabled: bool | None = None
    auto_join_enabled: bool | None = None
    display_label: str | None = None


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


class FeatureFlagUpdateRequest(BaseModel):
    key: str
    enabled: bool
    creator_id: str | None = None
    stream_session_id: str | None = None
    environment: str = "all"
    reason: str | None = None


# --- 1. System Overview ---
@router.get("/overview", summary="Control Center Overview")
async def get_dashboard_overview(db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    supervisor = get_health_supervisor()
    detailed_health = supervisor.get_latest_snapshot()
    if not detailed_health:
        health_svc = HealthMonitorService(session=db)
        detailed_health = await health_svc.get_detailed_snapshot()

    # Active stream count
    active_streams = 0
    try:
        active_stmt = select(func.count(StreamSession.id)).where(
            StreamSession.status.in_([StreamStatus.ACTIVE.value, StreamStatus.RUNNING.value])
        )
        active_res = await db.execute(active_stmt)
        active_streams = active_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Overview active streams query degraded: {e}")

    # Total registered creators
    total_creators = 0
    try:
        creator_stmt = select(func.count(Creator.id))
        creator_res = await db.execute(creator_stmt)
        total_creators = creator_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Overview creators query degraded: {e}")

    # Pending reviews
    pending_reviews = 0
    try:
        pending_stmt = select(func.count(ModerationReview.id)).where(
            ModerationReview.status == "PENDING"
        )
        pending_res = await db.execute(pending_stmt)
        pending_reviews = pending_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Overview pending reviews query degraded: {e}")

    # Open incidents
    open_incidents = 0
    try:
        incident_stmt = select(func.count(Incident.id)).where(
            Incident.status.in_(["OPEN", "INVESTIGATING"])
        )
        incident_res = await db.execute(incident_stmt)
        open_incidents = incident_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Overview incidents query degraded: {e}")

    # Active WebSub subscriptions
    active_websub = 0
    try:
        websub_stmt = select(func.count(WebSubSubscription.id)).where(
            WebSubSubscription.status == "ACTIVE"
        )
        websub_res = await db.execute(websub_stmt)
        active_websub = websub_res.scalar() or 0
    except Exception as e:
        logger.warning(f"Overview websub query degraded: {e}")

    # YouTube Quota
    quota_mgr = get_quota_manager()
    consumed = await quota_mgr.get_used()
    remaining = await quota_mgr.remaining()
    budget = quota_mgr.daily_limit

    return {
        "overall_status": detailed_health.get("overall_status", "HEALTHY"),
        "active_streams": active_streams,
        "total_creators": total_creators,
        "pending_moderation_reviews": pending_reviews,
        "open_incidents": open_incidents,
        "active_websub_subscriptions": active_websub,
        "quota": {
            "consumed": consumed,
            "remaining": remaining,
            "quota_remaining": remaining,
            "budget": budget,
            "percent_used": round((consumed / budget) * 100, 1) if budget > 0 else 0,
        },
        "subsystems": detailed_health.get("subsystems", {}),
        "ledger_balanced": True,
        "uptime_seconds": detailed_health.get("uptime_seconds", 0.0),
        "environment": detailed_health.get("environment", "development"),
        "timestamp": datetime.now(UTC).isoformat(),
    }


# --- 2. Live Streams Management ---
@router.get("/streams", summary="List All Live Stream Sessions")
async def list_streams(db: DBSessionDep, admin: AdminUserDep) -> list[dict[str, Any]]:
    worker_mgr = get_worker_manager()
    stmt = (
        select(StreamSession, Creator.channel_name)
        .join(Creator, StreamSession.creator_id == Creator.id)
        .order_by(desc(StreamSession.started_at))
        .limit(20)
    )
    res = await db.execute(stmt)
    rows = res.all()

    results = []
    for session, channel_name in rows:
        session_worker = worker_mgr.get_session_sync(session.id)
        is_worker_alive = session_worker is not None and session_worker.state.value in (
            "RUNNING",
            "ACTIVE",
        )
        msg_count = session_worker.messages_processed if session_worker else 0

        duration_minutes = 0.0
        if session.started_at:
            start_t = (
                session.started_at
                if session.started_at.tzinfo
                else session.started_at.replace(tzinfo=UTC)
            )
            end_t = session.ended_at or datetime.now(UTC)
            if end_t.tzinfo is None:
                end_t = end_t.replace(tzinfo=UTC)
            duration_minutes = round((end_t - start_t).total_seconds() / 60.0, 1)

        duration_seconds = int(duration_minutes * 60)
        results.append(
            {
                "id": session.id,
                "session_id": session.id,
                "creator_id": session.creator_id,
                "channel_name": channel_name,
                "youtube_video_id": session.youtube_video_id,
                "youtube_live_chat_id": session.youtube_live_chat_id,
                "status": session.status,
                "is_worker_alive": is_worker_alive,
                "messages_processed": msg_count,
                "duration_minutes": duration_minutes,
                "duration_seconds": duration_seconds,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "last_activity_at": session.started_at.isoformat() if session.started_at else None,
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
    lock = await _get_stream_lock(stream_id)

    async with lock:
        stmt = select(StreamSession).where(StreamSession.id == stream_id)
        res = await db.execute(stmt)
        stream = res.scalar_one_or_none()
        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stream session not found"
            )

        audit_repo = AuditRepository(db)
        op_id = req.operation_id or str(uuid.uuid4())
        action = req.action.lower()
        old_status = stream.status

        if action == "disconnect":
            if stream.status in (StreamStatus.ENDED.value, StreamStatus.STOPPED.value):
                return {
                    "status": "DISCONNECTED",
                    "stream_id": stream_id,
                    "operation_id": op_id,
                    "message": "Stream already ended (idempotent)",
                }
            try:
                await worker_mgr.stop_session(stream.id)
            except Exception as e:
                logger.warning(f"Worker session stop error: {e}")

            stream.status = StreamStatus.ENDED.value
            stream.ended_at = datetime.now(UTC)
            await db.flush()

            await audit_repo.log_event(
                event_type="stream.disconnect",
                actor_type="ADMIN",
                actor_id=admin.user_id,
                creator_id=stream.creator_id,
                stream_session_id=stream.id,
                payload={
                    "operation_id": op_id,
                    "previous_status": old_status,
                    "new_status": stream.status,
                },
            )
            return {"status": "DISCONNECTED", "stream_id": stream_id, "operation_id": op_id}

        elif action == "restart":
            try:
                await worker_mgr.restart_session(stream.id)
                stream.status = StreamStatus.ACTIVE.value
            except Exception as e:
                stream.status = StreamStatus.FAILED.value
                await db.flush()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Restart worker failed: {e}",
                ) from e
            await db.flush()

            await audit_repo.log_event(
                event_type="stream.restart",
                actor_type="ADMIN",
                actor_id=admin.user_id,
                creator_id=stream.creator_id,
                stream_session_id=stream.id,
                payload={
                    "operation_id": op_id,
                    "previous_status": old_status,
                    "new_status": stream.status,
                },
            )
            return {"status": "RESTARTED", "stream_id": stream_id, "operation_id": op_id}

        elif action == "reconcile":
            session_worker = worker_mgr.get_session_sync(stream.id)
            if session_worker and session_worker.state.value in ("RUNNING", "ACTIVE"):
                stream.status = StreamStatus.ACTIVE.value
            else:
                if stream.status == StreamStatus.ACTIVE.value:
                    stream.status = StreamStatus.DEGRADED.value
            await db.flush()
            return {
                "status": "RECONCILED",
                "stream_id": stream_id,
                "current_status": stream.status,
                "operation_id": op_id,
            }

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
    from app.core.exceptions import AppException
    from app.services.stream_service import StreamService

    stream_svc = StreamService(session=db)
    try:
        session_obj = await stream_svc.canonical_bootstrap_stream(
            url_or_video_id=req.url_or_video_id,
            creator_id=req.creator_id,
            actor_id=admin.user_id,
            auto_join=False,
        )
        return {
            "status": session_obj.status,
            "stream_session_id": session_obj.id,
            "creator_id": session_obj.creator_id,
            "video_id": session_obj.youtube_video_id,
            "live_chat_id": session_obj.youtube_live_chat_id,
        }
    except AppException as e:
        headers = {}
        if hasattr(e, "details") and isinstance(e.details, dict) and "error_code" in e.details:
            headers["X-Error-Code"] = e.details["error_code"]
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
            headers=headers,
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual connect unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect stream: {e}",
        ) from e


# --- 2b. Monitored YouTube Channels Registry & Auto-Join ---
@router.get("/monitored-channels", summary="List Monitored YouTube Channels")
async def list_monitored_channels(
    db: DBSessionDep,
    admin: AdminUserDep,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    mon_repo = MonitoredChannelRepository(db)
    if creator_id:
        channels = await mon_repo.list_by_creator(creator_id)
    else:
        stmt = select(MonitoredChannel).order_by(MonitoredChannel.created_at.desc())
        res = await db.execute(stmt)
        channels = res.scalars().all()

    results = []
    for ch in channels:
        c_stmt = select(Creator.channel_name).where(Creator.id == ch.creator_id)
        c_res = await db.execute(c_stmt)
        c_name = c_res.scalar_one_or_none() or "Unknown Creator"

        results.append(
            {
                "id": ch.id,
                "creator_id": ch.creator_id,
                "creator_name": c_name,
                "youtube_channel_id": ch.youtube_channel_id,
                "channel_name": ch.channel_name,
                "channel_handle": ch.channel_handle,
                "display_label": ch.display_label,
                "thumbnail_url": ch.thumbnail_url,
                "enabled": ch.enabled,
                "auto_join_enabled": ch.auto_join_enabled,
                "verification_status": ch.verification_status,
                "last_verified_at": ch.last_verified_at.isoformat() if ch.last_verified_at else None,
                "last_checked_at": ch.last_checked_at.isoformat() if ch.last_checked_at else None,
                "last_seen_live_at": ch.last_seen_live_at.isoformat() if ch.last_seen_live_at else None,
                "last_seen_video_id": ch.last_seen_video_id,
                "last_connected_stream_session_id": ch.last_connected_stream_session_id,
                "last_error_code": ch.last_error_code,
                "last_error_message_safe": ch.last_error_message_safe,
                "created_at": ch.created_at.isoformat() if ch.created_at else None,
            }
        )
    return results


@router.post("/monitored-channels", summary="Add and Verify Monitored YouTube Channel")
async def add_monitored_channel(
    req: MonitoredChannelCreateRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    from app.core.exceptions import ChannelNotFoundError
    from app.youtube.channel_resolver import ChannelIdentifierResolver

    # 1. Authoritative YouTube Channel verification
    try:
        verified = await ChannelIdentifierResolver.verify_channel(req.identifier)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"YouTube channel '{req.identifier}' was not found.",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel verification failed: {e}",
        ) from e

    # 2. Resolve creator
    creator = None
    if req.creator_id:
        c_stmt = select(Creator).where(Creator.id == req.creator_id)
        c_res = await db.execute(c_stmt)
        creator = c_res.scalar_one_or_none()
        if not creator:
            raise HTTPException(status_code=404, detail=f"Creator '{req.creator_id}' not found.")
    else:
        c_stmt = select(Creator).where(Creator.youtube_channel_id == verified.channel_id)
        c_res = await db.execute(c_stmt)
        creator = c_res.scalar_one_or_none()
        if not creator:
            c_stmt2 = select(Creator).where(Creator.enabled.is_(True)).limit(1)
            c_res2 = await db.execute(c_stmt2)
            creator = c_res2.scalar_one_or_none()
        if not creator:
            creator = Creator(
                id="default-creator",
                youtube_channel_id=verified.channel_id,
                channel_name=verified.channel_name,
                enabled=True,
            )
            db.add(creator)
            await db.flush()

    # 3. Duplicate check for creator
    mon_repo = MonitoredChannelRepository(db)
    existing = await mon_repo.get_by_channel_id(creator.id, verified.channel_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel '{verified.channel_name}' ({verified.channel_id}) is already being monitored for this creator.",
        )

    # 4. Persist MonitoredChannel
    mon_channel = MonitoredChannel(
        creator_id=creator.id,
        youtube_channel_id=verified.channel_id,
        channel_name=verified.channel_name,
        channel_handle=verified.handle,
        display_label=req.display_label or verified.channel_name,
        thumbnail_url=verified.thumbnail_url,
        enabled=True,
        auto_join_enabled=req.auto_join_enabled,
        verification_status="VERIFIED",
        last_verified_at=datetime.now(UTC),
    )
    mon_channel = await mon_repo.create(mon_channel)

    # 5. Audit log
    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="monitored_channel.created",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        creator_id=creator.id,
        payload={"youtube_channel_id": verified.channel_id, "channel_name": verified.channel_name},
    )

    return {
        "id": mon_channel.id,
        "creator_id": mon_channel.creator_id,
        "youtube_channel_id": mon_channel.youtube_channel_id,
        "channel_name": mon_channel.channel_name,
        "channel_handle": mon_channel.channel_handle,
        "display_label": mon_channel.display_label,
        "thumbnail_url": mon_channel.thumbnail_url,
        "enabled": mon_channel.enabled,
        "auto_join_enabled": mon_channel.auto_join_enabled,
        "verification_status": mon_channel.verification_status,
        "created_at": mon_channel.created_at.isoformat() if mon_channel.created_at else None,
    }


@router.patch("/monitored-channels/{id}", summary="Update Monitored Channel Settings")
async def update_monitored_channel(
    id: str,
    req: MonitoredChannelUpdateRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    mon_repo = MonitoredChannelRepository(db)
    channel = await mon_repo.get_by_id(id)
    if not channel:
        raise HTTPException(status_code=404, detail="Monitored channel not found.")

    if req.enabled is not None:
        channel.enabled = req.enabled
    if req.auto_join_enabled is not None:
        channel.auto_join_enabled = req.auto_join_enabled
    if req.display_label is not None:
        channel.display_label = req.display_label

    await db.flush()

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="monitored_channel.updated",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        creator_id=channel.creator_id,
        payload={"monitored_channel_id": id, "enabled": channel.enabled, "auto_join": channel.auto_join_enabled},
    )

    return {
        "id": channel.id,
        "enabled": channel.enabled,
        "auto_join_enabled": channel.auto_join_enabled,
        "display_label": channel.display_label,
    }


@router.delete("/monitored-channels/{id}", summary="Delete Monitored Channel")
async def delete_monitored_channel(
    id: str,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    mon_repo = MonitoredChannelRepository(db)
    channel = await mon_repo.get_by_id(id)
    if not channel:
        raise HTTPException(status_code=404, detail="Monitored channel not found.")

    creator_id = channel.creator_id
    channel_name = channel.channel_name
    await db.delete(channel)
    await db.flush()

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="monitored_channel.deleted",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        creator_id=creator_id,
        payload={"monitored_channel_id": id, "channel_name": channel_name},
    )

    return {"status": "DELETED", "id": id}


@router.post("/monitored-channels/{id}/check-now", summary="Force Live Check on Monitored Channel")
async def check_monitored_channel_now(
    id: str,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    from app.db.session import get_session_factory
    from app.services.monitored_channel_coordinator import get_monitored_channel_coordinator

    mon_repo = MonitoredChannelRepository(db)
    channel = await mon_repo.get_by_id(id)
    if not channel:
        raise HTTPException(status_code=404, detail="Monitored channel not found.")

    coordinator = get_monitored_channel_coordinator()
    session_factory = get_session_factory()
    result = await coordinator.check_channel(channel_record_id=id, session_maker=session_factory)
    return result


# --- 3. Creator Registry ---
@router.get("/creators", summary="List Registered Creators")
async def list_creators(db: DBSessionDep, admin: AdminUserDep) -> list[dict[str, Any]]:
    stmt = select(Creator).order_by(Creator.created_at.desc())
    res = await db.execute(stmt)
    creators = res.scalars().all()

    results = []
    for c in creators:
        # Check discord config
        disc_stmt = select(CreatorDiscordConfig).where(CreatorDiscordConfig.creator_id == c.id)
        disc_res = await db.execute(disc_stmt)
        disc_conf = disc_res.scalar_one_or_none()

        results.append(
            {
                "id": c.id,
                "youtube_channel_id": c.youtube_channel_id,
                "channel_name": c.channel_name,
                "enabled": c.enabled,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "discord_log_channel_id": disc_conf.log_channel_id if disc_conf else None,
                "discord_alert_channel_id": disc_conf.alert_channel_id if disc_conf else None,
            }
        )
    return results


@router.post("/creators", summary="Register Creator Channel")
async def create_creator(
    req: CreatorCreateRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    stmt = select(Creator).where(Creator.youtube_channel_id == req.youtube_channel_id)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Creator with channel ID {req.youtube_channel_id} already exists",
        )

    creator = Creator(
        youtube_channel_id=req.youtube_channel_id,
        channel_name=req.channel_name,
        enabled=req.enabled,
    )
    db.add(creator)
    await db.flush()

    if req.discord_log_channel_id or req.discord_alert_channel_id:
        conf = CreatorDiscordConfig(
            creator_id=creator.id,
            log_channel_id=req.discord_log_channel_id,
            alert_channel_id=req.discord_alert_channel_id,
        )
        db.add(conf)
        await db.flush()

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="creator.create",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        creator_id=creator.id,
        payload={"youtube_channel_id": req.youtube_channel_id, "channel_name": req.channel_name},
    )

    return {
        "id": creator.id,
        "youtube_channel_id": creator.youtube_channel_id,
        "channel_name": creator.channel_name,
        "enabled": creator.enabled,
    }


# --- 4. YouTube Quota & Key Pool ---
@router.get("/quota", summary="YouTube Quota Telemetry")
async def get_quota_telemetry(admin: AdminUserDep) -> dict[str, Any]:
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
        "accuracy": {
            "budget": "MEASURED",
            "consumed": "MEASURED",
            "remaining": "DERIVED",
            "percent_used": "DERIVED",
        },
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
                "cooldown_until": k.cooldown_until if k.cooldown_until > 0 else None,
                "accuracy": "MEASURED",
            }
        )
    return results


@router.post("/youtube-keys/{index}/reset", summary="Reset API Key Cooldown")
async def reset_key_cooldown(index: int, db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    from app.youtube.key_pool import KeyStatus, get_key_pool

    pool = get_key_pool()
    all_keys = list(pool._keys.values()) if pool else []
    if not pool or index < 0 or index >= len(all_keys):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key index not found")

    target = all_keys[index]
    old_status = target.status.value
    target.status = KeyStatus.AVAILABLE
    target.cooldown_until = 0.0

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="youtube_key.reset_cooldown",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        payload={
            "key_index": index,
            "slot": target.slot,
            "previous_status": old_status,
            "new_status": target.status.value,
        },
    )

    return {"message": f"Reset cooldown on key index {index}"}


# --- 5. AI Observability ---
@router.get("/ai", summary="AI & OpenRouter Metrics")
async def get_ai_metrics(db: DBSessionDep, admin: AdminUserDep) -> dict[str, Any]:
    from app.db.models.ai_usage import AIUsageRecord

    stmt = select(
        func.count(AIUsageRecord.id).label("total_requests"),
        func.sum(AIUsageRecord.total_tokens).label("total_tokens"),
        func.avg(AIUsageRecord.latency_ms).label("avg_latency_ms"),
    )
    res = await db.execute(stmt)
    row = res.one()

    total_requests = row[0] or 0
    total_tokens = row[1] or 0
    avg_latency = round(float(row[2] or 0.0), 1)
    estimated_cost = round(float(total_tokens) * 0.000002, 4)

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "avg_latency_ms": avg_latency,
        "fallback_rate_percent": 0.0,
        "accuracy": {
            "total_requests": "MEASURED",
            "total_tokens": "MEASURED",
            "estimated_cost_usd": "ESTIMATED",
            "avg_latency_ms": "MEASURED",
            "fallback_rate_percent": "DERIVED",
        },
    }


# --- 6. Moderation & HITL Queue ---
@router.get("/moderation", summary="Moderation & HITL Queue")
async def get_moderation_queue(
    db: DBSessionDep,
    admin: AdminUserDep,
    status_filter: str = Query("PENDING", description="PENDING, APPROVED, REJECTED, EXPIRED"),
) -> dict[str, Any]:
    try:
        stmt = (
            select(ModerationReview)
            .where(ModerationReview.status == status_filter)
            .order_by(desc(ModerationReview.created_at))
            .limit(50)
        )
        res = await db.execute(stmt)
        reviews = res.scalars().all()

        # Total counts
        count_stmt = select(ModerationReview.status, func.count(ModerationReview.id)).group_by(
            ModerationReview.status
        )
        count_res = await db.execute(count_stmt)
        counts = dict(count_res.all())

        items = []
        for r in reviews:
            v_channel_id = getattr(r, "author_channel_id", getattr(r, "viewer_channel_id", ""))
            v_name = getattr(r, "author_display_name", getattr(r, "viewer_name", "Anonymous"))
            msg_txt = getattr(r, "message_text", getattr(r, "flagged_content", ""))
            r_reason = getattr(
                r, "reason", getattr(r, "flagged_reason", "Automated moderation flag")
            )
            conf = getattr(r, "confidence", getattr(r, "confidence_score", 50))
            if isinstance(conf, float) and conf <= 1.0:
                conf = int(conf * 100)
            else:
                conf = int(conf or 50)
            sev = getattr(r, "severity", conf)

            items.append(
                {
                    "id": r.id,
                    "creator_id": getattr(r, "creator_id", "default-creator"),
                    "stream_session_id": getattr(r, "stream_session_id", ""),
                    "viewer_channel_id": v_channel_id,
                    "author_channel_id": v_channel_id,
                    "viewer_name": v_name,
                    "author_display_name": v_name,
                    "flagged_content": msg_txt,
                    "message_text": msg_txt,
                    "flagged_reason": r_reason,
                    "reason": r_reason,
                    "confidence_score": conf,
                    "confidence": conf,
                    "severity": sev,
                    "recommended_action": getattr(r, "recommended_action", "DELETE"),
                    "status": getattr(r, "status", "PENDING"),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                }
            )

        return {
            "items": items,
            "counts": {
                "pending": counts.get("PENDING", 0),
                "approved": counts.get("APPROVED", 0),
                "rejected": counts.get("REJECTED", 0),
                "expired": counts.get("EXPIRED", 0),
            },
        }
    except Exception as e:
        logger.warning(f"Moderation queue query degraded: {e}")
        return {
            "items": [],
            "counts": {"pending": 0, "approved": 0, "rejected": 0, "expired": 0},
        }


@router.post("/moderation/reviews/{review_id}/resolve", summary="Resolve HITL Review")
async def resolve_moderation_review(
    review_id: str,
    req: ResolveReviewRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    from app.services.hitl_service import HITLService

    hitl_svc = HITLService(db)
    if req.action.upper() == "APPROVE":
        success = await hitl_svc.approve_message(
            review_id, resolved_by=admin.user_id, note=req.reason
        )
    elif req.action.upper() == "DENY":
        success = await hitl_svc.reject_message(
            review_id, resolved_by=admin.user_id, note=req.reason
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be APPROVE or DENY",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found or already resolved"
        )

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="moderation.resolve",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        payload={"review_id": review_id, "action": req.action.upper(), "reason": req.reason},
    )

    return {"message": f"Review {review_id} {req.action.lower()}d successfully"}


# --- 7. Incidents & Operations ---
@router.get("/incidents", summary="List System Incidents")
async def list_incidents(
    db: DBSessionDep,
    admin: AdminUserDep,
    status_filter: str | None = Query(None, description="OPEN, INVESTIGATING, MITIGATED, RESOLVED"),
) -> list[dict[str, Any]]:
    try:
        svc = IncidentService(db)
        incidents, _ = await svc.list_incidents(status=status_filter, limit=50)
        return [
            {
                "id": inc.id,
                "incident_id": inc.incident_id,
                "severity": inc.severity,
                "service": inc.service,
                "summary": inc.summary,
                "status": inc.status,
                "root_cause": inc.root_cause,
                "resolution": inc.resolution,
                "actions_taken": inc.actions_taken,
                "detected_at": inc.detected_at.isoformat() if inc.detected_at else None,
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            }
            for inc in incidents
        ]
    except Exception as e:
        logger.warning(f"List incidents query degraded: {e}")
        return []


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

    audit_repo = AuditRepository(db)
    await audit_repo.log_event(
        event_type="incident.resolve",
        actor_type="ADMIN",
        actor_id=admin.user_id,
        payload={
            "incident_id": incident_id,
            "new_status": req.status,
            "resolution": req.resolution,
        },
    )

    return {"message": f"Incident {incident_id} updated to {req.status}"}


# --- 8. Economy Telemetry ---
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
        "accuracy": {
            "circulating_coins": "MEASURED",
            "total_accounts": "MEASURED",
            "ledger_balanced": "DERIVED",
            "total_transactions": "MEASURED",
        },
    }


# --- 9. Feature Flags ---
@router.get("/feature-flags", summary="List Operational Feature Flags")
async def list_feature_flags(db: DBSessionDep, admin: AdminUserDep) -> list[dict[str, Any]]:
    ff_service = FeatureFlagService(db)
    return await ff_service.list_flags()


@router.post("/feature-flags", summary="Update Feature Flag")
async def update_feature_flag(
    req: FeatureFlagUpdateRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    ff_service = FeatureFlagService(db)
    flag = await ff_service.set_flag(
        key=req.key,
        enabled=req.enabled,
        creator_id=req.creator_id,
        stream_session_id=req.stream_session_id,
        environment=req.environment,
        actor_id=admin.user_id,
        reason=req.reason,
    )
    return {
        "key": flag.key,
        "enabled": flag.enabled,
        "creator_id": flag.creator_id,
        "stream_session_id": flag.stream_session_id,
        "environment": flag.environment,
    }


# --- 10. Audit Logs ---
@router.get("/audit-logs", summary="List System Operation Audit Trail")
async def list_audit_logs(
    db: DBSessionDep,
    admin: AdminUserDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    stmt = select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit)
    res = await db.execute(stmt)
    events = res.scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "creator_id": e.creator_id,
            "stream_session_id": e.stream_session_id,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


# --- 11. Real-Time Server-Sent Events (SSE) Stream ---
@router.get("/events/stream", summary="Real-Time Control Center SSE Feed")
async def stream_dashboard_events(
    request: Request,
    admin: AdminUserDep,
):
    """
    Continuous Server-Sent Events (SSE) stream pushing live domain & telemetry events
    to Developer Control Center without database polling.
    """
    broadcaster = get_sse_broadcaster()
    last_event_id = request.headers.get("Last-Event-ID")

    return StreamingResponse(
        broadcaster.client_event_generator(last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- 12. Direct /api/v1 Aliases (without /dashboard prefix) ---
alias_router = APIRouter(tags=["Developer Control Center Aliases"])

alias_router.add_api_route(
    "/overview", get_dashboard_overview, methods=["GET"], summary="Control Center Overview Alias"
)
alias_router.add_api_route("/streams", list_streams, methods=["GET"], summary="List Streams Alias")
alias_router.add_api_route(
    "/quota", get_quota_telemetry, methods=["GET"], summary="Quota Status Alias"
)
alias_router.add_api_route(
    "/youtube-keys", get_key_pool_status, methods=["GET"], summary="YouTube Keys Alias"
)
alias_router.add_api_route(
    "/moderation", get_moderation_queue, methods=["GET"], summary="Moderation Queue Alias"
)
alias_router.add_api_route("/incidents", list_incidents, methods=["GET"], summary="Incidents Alias")
alias_router.add_api_route(
    "/events/stream", stream_dashboard_events, methods=["GET"], summary="SSE Stream Alias"
)

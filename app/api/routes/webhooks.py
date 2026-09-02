"""WebSub webhook receiver endpoints for YouTube PubSubHubbub verification and notifications."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.api.schemas.webhooks import WebSubNotificationAck
from app.core.exceptions import InvalidArgumentError
from app.core.logging import get_logger
from app.db.models.websub_subscription import WebSubStatus
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.discovery_repo import DiscoveryRepository
from app.db.repositories.websub_repo import WebSubRepository
from app.events.bus import get_event_bus
from app.events.schemas import YouTubeWebSubNotificationEvent
from app.youtube.websub.dedupe import get_websub_deduplicator
from app.youtube.websub.parser import WebSubParser

logger = get_logger("app.api.routes.webhooks")
router = APIRouter(prefix="/webhooks/youtube", tags=["Webhooks"])


@router.get("/websub", response_class=PlainTextResponse)
async def verify_websub_subscription(
    hub_mode: str = Query(alias="hub.mode"),
    hub_topic: str = Query(alias="hub.topic"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_lease_seconds: int | None = Query(default=None, alias="hub.lease_seconds"),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """
    Handle WebSub subscription verification from Google PubSubHubbub hub.
    Validates topic, updates subscription state, and returns exact challenge.
    """
    logger.info(f"Received WebSub verification GET: mode='{hub_mode}', topic='{hub_topic}'")

    if hub_mode not in ("subscribe", "unsubscribe"):
        logger.warning(f"Invalid WebSub hub.mode: '{hub_mode}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid hub.mode '{hub_mode}'"
        )

    repo = WebSubRepository(session)
    sub = await repo.get_by_topic_url(hub_topic)

    if not sub:
        # Fallback: check if topic contains a known channel ID
        if "channel_id=" in hub_topic:
            channel_id = hub_topic.split("channel_id=")[-1].strip()
            sub = await repo.get_by_channel_id(channel_id)

    if not sub:
        logger.warning(f"WebSub verification rejected: Topic '{hub_topic}' is not registered.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not recognized")

    now = datetime.now(UTC)
    if hub_mode == "subscribe":
        lease = hub_lease_seconds or sub.lease_seconds or 864000
        expires_at = now + timedelta(seconds=lease)
        await repo.update_status(
            sub.id,
            status=WebSubStatus.ACTIVE,
            lease_seconds=lease,
            lease_expires_at=expires_at,
        )
        logger.info(
            f"WebSub subscription for channel '{sub.channel_id}' verified as ACTIVE (lease: {lease}s)."
        )
    else:
        await repo.update_status(sub.id, status=WebSubStatus.DISABLED)
        logger.info(
            f"WebSub subscription for channel '{sub.channel_id}' marked as DISABLED (unsubscribed)."
        )

    return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)


@router.post("/websub", response_model=WebSubNotificationAck)
async def receive_websub_notification(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> WebSubNotificationAck:
    """
    Receive Atom XML feed notification from Google PubSubHubbub.
    Parses payload securely, deduplicates, records discovery event, and publishes internal event.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty request body")

    try:
        notification = WebSubParser.parse_atom_feed(body)
    except InvalidArgumentError as e:
        logger.error(f"Malformed WebSub XML received: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    logger.info(
        f"WebSub notification received: channel='{notification.channel_id}', "
        f"video='{notification.video_id}', title='{notification.title[:30]}...'"
    )

    # Distributed deduplication check
    deduplicator = get_websub_deduplicator()
    is_duplicate = await deduplicator.is_duplicate_or_record(notification.dedupe_hash)
    if is_duplicate:
        return WebSubNotificationAck(
            status="received",
            channel_id=notification.channel_id,
            video_id=notification.video_id,
            deduplicated=True,
        )

    # Correlate with creator record
    creator_repo = CreatorRepository(session)
    creator = await creator_repo.get_by_channel_id(notification.channel_id)
    creator_id = creator.id if creator else None

    # Record discovery event in database
    discovery_repo = DiscoveryRepository(session)
    event_record = await discovery_repo.record_event(
        channel_id=notification.channel_id,
        video_id=notification.video_id,
        dedupe_hash=notification.dedupe_hash,
        creator_id=creator_id,
        event_type="WEBSUB_NOTIFICATION",
        source="websub",
        payload={
            "title": notification.title,
            "feed_id": notification.feed_id,
            "published_at": notification.published_at.isoformat()
            if notification.published_at
            else None,
            "updated_at": notification.updated_at.isoformat() if notification.updated_at else None,
        },
    )

    # Publish typed internal event to EventBus
    bus = get_event_bus()
    await bus.publish(
        YouTubeWebSubNotificationEvent(
            creator_id=creator_id,
            channel_id=notification.channel_id,
            video_id=notification.video_id,
            title=notification.title,
            dedupe_hash=notification.dedupe_hash,
            payload={"discovery_event_id": event_record.id},
        )
    )

    return WebSubNotificationAck(
        status="received",
        channel_id=notification.channel_id,
        video_id=notification.video_id,
        deduplicated=False,
        discovery_event_id=event_record.id,
    )

"""Repository for YouTube discovery events."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.discovery_event import YouTubeDiscoveryEvent
from app.db.repositories.base import BaseRepository


class DiscoveryRepository(BaseRepository[YouTubeDiscoveryEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(YouTubeDiscoveryEvent, session)

    async def get_by_dedupe_hash(self, dedupe_hash: str) -> YouTubeDiscoveryEvent | None:
        """Fetch discovery event by dedupe hash."""
        result = await self.session.execute(
            select(YouTubeDiscoveryEvent).where(YouTubeDiscoveryEvent.dedupe_hash == dedupe_hash)
        )
        return result.scalars().first()

    async def list_unprocessed(self, limit: int = 50) -> list[YouTubeDiscoveryEvent]:
        """Fetch unprocessed discovery events."""
        result = await self.session.execute(
            select(YouTubeDiscoveryEvent)
            .where(YouTubeDiscoveryEvent.processed.is_(False))
            .order_by(YouTubeDiscoveryEvent.received_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_event(
        self,
        channel_id: str,
        video_id: str,
        dedupe_hash: str,
        creator_id: str | None = None,
        event_type: str = "WEBSUB_NOTIFICATION",
        source: str = "websub",
        payload: dict[str, Any] | None = None,
    ) -> YouTubeDiscoveryEvent:
        """Record a new discovery event."""
        event = YouTubeDiscoveryEvent(
            creator_id=creator_id,
            channel_id=channel_id,
            video_id=video_id,
            dedupe_hash=dedupe_hash,
            event_type=event_type,
            source=source,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def mark_processed(self, event_id: str) -> YouTubeDiscoveryEvent | None:
        """Mark discovery event as processed."""
        event = await self.get_by_id(event_id)
        if event:
            event.processed = True
            event.processed_at = datetime.now()
            await self.session.flush()
        return event

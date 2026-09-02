"""Creator service managing creator channels, configurations, and lifecycle events."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from app.core.logging import get_logger
from app.db.models.creator import Creator
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.creator_repo import CreatorRepository
from app.events.bus import get_event_bus
from app.events.schemas import CreatorRegisteredEvent, CreatorUpdatedEvent

logger = get_logger("app.services.creator")


class CreatorService:
    """Business logic for managing registered creators."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.creator_repo = CreatorRepository(session)
        self.audit_repo = AuditRepository(session)
        self.event_bus = get_event_bus()

    async def register_creator(
        self,
        youtube_channel_id: str,
        channel_name: str,
        enabled: bool = True,
        actor_id: str = "SYSTEM",
    ) -> Creator:
        """Register a new YouTube creator."""
        existing = await self.creator_repo.get_by_youtube_channel_id(youtube_channel_id)
        if existing:
            raise EntityAlreadyExistsError("Creator", youtube_channel_id)

        creator = await self.creator_repo.create(
            youtube_channel_id=youtube_channel_id,
            channel_name=channel_name,
            enabled=enabled,
        )

        await self.audit_repo.log_event(
            event_type="CREATOR_REGISTERED",
            actor_type="DEVELOPER",
            actor_id=actor_id,
            creator_id=creator.id,
            payload={"youtube_channel_id": youtube_channel_id, "channel_name": channel_name},
        )

        await self.event_bus.publish(
            CreatorRegisteredEvent(
                creator_id=creator.id,
                payload={"youtube_channel_id": youtube_channel_id, "channel_name": channel_name},
            )
        )

        logger.info(f"Registered new creator '{channel_name}' ({youtube_channel_id}) with ID {creator.id}")
        return creator

    async def get_creator(self, creator_id: str) -> Creator:
        """Fetch creator by primary key or raise EntityNotFoundError."""
        creator = await self.creator_repo.get_by_id(creator_id)
        if not creator:
            raise EntityNotFoundError("Creator", creator_id)
        return creator

    async def list_creators(self, limit: int = 100, offset: int = 0) -> Sequence[Creator]:
        """List creators with pagination."""
        return await self.creator_repo.list_all(limit=limit, offset=offset)

    async def update_creator(
        self,
        creator_id: str,
        channel_name: str | None = None,
        enabled: bool | None = None,
        actor_id: str = "SYSTEM",
    ) -> Creator:
        """Update creator properties."""
        creator = await self.get_creator(creator_id)
        changes: dict[str, Any] = {}

        if channel_name is not None and channel_name != creator.channel_name:
            creator.channel_name = channel_name
            changes["channel_name"] = channel_name

        if enabled is not None and enabled != creator.enabled:
            creator.enabled = enabled
            changes["enabled"] = enabled

        if changes:
            await self.session.flush()
            await self.audit_repo.log_event(
                event_type="CREATOR_UPDATED",
                actor_type="CREATOR",
                actor_id=actor_id,
                creator_id=creator.id,
                payload=changes,
            )
            await self.event_bus.publish(
                CreatorUpdatedEvent(
                    creator_id=creator.id,
                    payload=changes,
                )
            )

        return creator

    async def delete_creator(self, creator_id: str, actor_id: str = "SYSTEM") -> None:
        """Delete creator and cascade child stream sessions."""
        creator = await self.get_creator(creator_id)
        await self.audit_repo.log_event(
            event_type="CREATOR_DELETED",
            actor_type="DEVELOPER",
            actor_id=actor_id,
            creator_id=creator.id,
            payload={"channel_name": creator.channel_name},
        )
        await self.creator_repo.delete(creator)

"""AuditEvent repository."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_event import AuditEvent
from app.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditEvent, session)

    async def log_event(
        self,
        event_type: str,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
        creator_id: str | None = None,
        stream_session_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create and store an audit log entry."""
        return await self.create(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            payload=payload or {},
        )

    async def list_by_stream(
        self, stream_session_id: str, limit: int = 100
    ) -> Sequence[AuditEvent]:
        """Fetch audit trail for a specific stream."""
        result = await self.session.execute(
            select(AuditEvent)
            .where(AuditEvent.stream_session_id == stream_session_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

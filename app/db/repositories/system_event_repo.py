"""SystemEvent repository."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.system_event import SystemEvent, SystemSeverity
from app.db.repositories.base import BaseRepository


class SystemEventRepository(BaseRepository[SystemEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(SystemEvent, session)

    async def log_system_event(
        self,
        event_type: str,
        message: str,
        severity: SystemSeverity = SystemSeverity.INFO,
        service: str = "ai-modrator",
        stream_session_id: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> SystemEvent:
        """Persist a system warning, error, or critical event."""
        return await self.create(
            event_type=event_type,
            message=message,
            severity=severity.value,
            service=service,
            stream_session_id=stream_session_id,
            metadata_payload=metadata_payload or {},
        )

    async def list_recent(self, limit: int = 50, severity: SystemSeverity | None = None) -> Sequence[SystemEvent]:
        """Fetch recent system events, optionally filtered by severity."""
        query = select(SystemEvent)
        if severity:
            query = query.where(SystemEvent.severity == severity.value)
        query = query.order_by(SystemEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

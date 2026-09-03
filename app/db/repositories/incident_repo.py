"""Incident repository for CRUD operations and query filters."""

from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.incident import Incident


class IncidentRepository:
    """Repository managing incident records, state changes, and filtering."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_incident(
        self,
        incident_id: str,
        severity: str,
        service: str,
        summary: str,
        creator_id: str | None = None,
        stream_session_id: str | None = None,
        root_cause: str | None = None,
        actions_taken: list[str] | None = None,
    ) -> Incident:
        incident = Incident(
            incident_id=incident_id,
            severity=severity,
            service=service,
            summary=summary,
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            root_cause=root_cause,
            actions_taken=actions_taken or [],
            status="OPEN",
            detected_at=datetime.now(UTC),
        )
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get_by_incident_id(self, incident_id: str) -> Incident | None:
        stmt = select(Incident).where(Incident.incident_id == incident_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_incidents(self, limit: int = 50) -> list[Incident]:
        stmt = (
            select(Incident)
            .where(Incident.status.in_(["OPEN", "INVESTIGATING"]))
            .order_by(desc(Incident.detected_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_incidents(
        self,
        service: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Incident], int]:
        stmt = select(Incident)
        count_stmt = select(func.count(Incident.id))

        if service:
            stmt = stmt.where(Incident.service == service)
            count_stmt = count_stmt.where(Incident.service == service)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
            count_stmt = count_stmt.where(Incident.severity == severity)
        if status:
            stmt = stmt.where(Incident.status == status)
            count_stmt = count_stmt.where(Incident.status == status)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = stmt.order_by(desc(Incident.detected_at)).offset(offset).limit(limit)
        items_res = await self.session.execute(stmt)
        return list(items_res.scalars().all()), total

    async def update_status(
        self,
        incident_id: str,
        status: str,
        resolution: str | None = None,
        root_cause: str | None = None,
        action: str | None = None,
    ) -> Incident | None:
        incident = await self.get_by_incident_id(incident_id)
        if not incident:
            return None

        incident.status = status
        now = datetime.now(UTC)
        if status == "MITIGATED" and not incident.mitigated_at:
            incident.mitigated_at = now
        elif status in ("RESOLVED", "CLOSED") and not incident.resolved_at:
            incident.resolved_at = now

        if resolution:
            incident.resolution = resolution
        if root_cause:
            incident.root_cause = root_cause
        if action:
            current_actions = list(incident.actions_taken)
            current_actions.append(f"[{now.isoformat()}] {action}")
            incident.actions_taken = current_actions

        await self.session.flush()
        return incident

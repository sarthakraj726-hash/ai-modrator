"""Incident management service for operational tracking, deduplication, and mitigation."""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidArgumentError
from app.core.logging import get_logger
from app.db.models.incident import Incident
from app.db.repositories.incident_repo import IncidentRepository
from app.events.bus import EventBus, get_event_bus
from app.events.schemas import SystemCriticalEvent

logger = get_logger("app.services.incidents")

# Strict legal transitions for incident lifecycle state machine
LEGAL_INCIDENT_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"INVESTIGATING", "MITIGATED", "RESOLVED", "CLOSED"},
    "INVESTIGATING": {"MITIGATED", "RESOLVED", "CLOSED"},
    "MITIGATED": {"INVESTIGATING", "RESOLVED", "CLOSED"},
    "RESOLVED": {"CLOSED", "OPEN"},
    "CLOSED": {"OPEN"},
}

_incident_creation_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


class IncidentService:
    """
    Manages production incident lifecycle:
    - Auto-deduplication to prevent alert storms.
    - Strict state transitions (OPEN -> INVESTIGATING -> MITIGATED -> RESOLVED -> CLOSED).
    - Concurrency-safe incident creation preventing race conditions.
    - EventBus broadcasting for real-time dashboard and Discord notifications.
    """

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None):
        self.session = session
        self.repo = IncidentRepository(session)
        self.event_bus = event_bus or get_event_bus()

    async def _get_creation_lock(self, fingerprint: str) -> asyncio.Lock:
        async with _locks_lock:
            if fingerprint not in _incident_creation_locks:
                _incident_creation_locks[fingerprint] = asyncio.Lock()
            return _incident_creation_locks[fingerprint]

    async def report_incident(
        self,
        severity: str,
        service: str,
        summary: str,
        creator_id: str | None = None,
        stream_session_id: str | None = None,
        root_cause: str | None = None,
        action: str | None = None,
    ) -> tuple[Incident, bool]:
        """
        Report an incident. If an active incident (OPEN/INVESTIGATING) already exists
        for the given service and creator, deduplicate and append actions instead of creating a duplicate.
        Thread/task-safe against concurrent reporting.
        Returns: (Incident, is_new)
        """
        fingerprint = f"{service}:{creator_id or 'global'}:{stream_session_id or 'none'}"
        lock = await self._get_creation_lock(fingerprint)

        async with lock:
            # Check for existing active incident on this service
            active_incidents = await self.repo.get_active_incidents()
            for inc in active_incidents:
                if inc.service == service and inc.creator_id == creator_id:
                    logger.info(
                        f"Deduplicated incident on {service} into existing active incident {inc.incident_id}"
                    )
                    now_str = datetime.now(UTC).isoformat()
                    dedupe_note = f"[{now_str}] Recurring occurrence detected: {summary}"
                    if action:
                        dedupe_note += f" | Action: {action}"
                    await self.repo.update_status(inc.incident_id, inc.status, action=dedupe_note)
                    return inc, False

            # Generate human-readable incident identifier
            incident_id = (
                f"INC-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )
            actions = [f"[{datetime.now(UTC).isoformat()}] Detected: {summary}"]
            if action:
                actions.append(f"[{datetime.now(UTC).isoformat()}] Initial action: {action}")

            incident = await self.repo.create_incident(
                incident_id=incident_id,
                severity=severity,
                service=service,
                summary=summary,
                creator_id=creator_id,
                stream_session_id=stream_session_id,
                root_cause=root_cause,
                actions_taken=actions,
            )

            logger.warn(
                f"Created new incident {incident_id} [{severity}] for service {service}: {summary}"
            )

            # Broadcast via EventBus
            event = SystemCriticalEvent(
                creator_id=creator_id,
                stream_session_id=stream_session_id,
                message=f"[{incident.severity}] {incident.service}: {incident.summary}",
                payload={
                    "incident_id": incident.incident_id,
                    "severity": incident.severity,
                    "service": incident.service,
                    "summary": incident.summary,
                    "status": incident.status,
                    "action": "CREATED",
                },
            )
            await self.event_bus.publish(event)
            return incident, True

    async def update_status(
        self,
        incident_id: str,
        status: str,
        resolution: str | None = None,
        root_cause: str | None = None,
        action: str | None = None,
    ) -> Incident | None:
        """Update incident lifecycle state with transition validation."""
        target_status = status.upper()

        # Fetch current incident
        current = await self.repo.get_by_incident_id(incident_id)
        if not current:
            return None

        current_status = current.status.upper()
        if current_status != target_status:
            allowed = LEGAL_INCIDENT_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                raise InvalidArgumentError(
                    f"Illegal incident transition from {current_status} to {target_status}. "
                    f"Allowed: {allowed}"
                )

        incident = await self.repo.update_status(
            incident_id=incident_id,
            status=target_status,
            resolution=resolution,
            root_cause=root_cause,
            action=action,
        )
        if not incident:
            return None

        logger.info(f"Updated incident {incident_id} to status {target_status}")

        if target_status in ("RESOLVED", "CLOSED"):
            event = SystemCriticalEvent(
                creator_id=incident.creator_id,
                stream_session_id=incident.stream_session_id,
                message=f"[{target_status}] {incident.service}: {incident.summary}",
                payload={
                    "incident_id": incident.incident_id,
                    "severity": incident.severity,
                    "service": incident.service,
                    "summary": incident.summary,
                    "status": incident.status,
                    "resolution": incident.resolution,
                    "action": target_status,
                },
            )
            await self.event_bus.publish(event)

        return incident

    async def list_incidents(
        self,
        service: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Incident], int]:
        return await self.repo.list_incidents(
            service=service,
            severity=severity,
            status=status,
            limit=limit,
            offset=offset,
        )

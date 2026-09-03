"""Unit tests for IncidentService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.events.bus import EventBus
from app.services.incidents import IncidentService


@pytest.fixture
async def incident_creator(db_session: AsyncSession) -> Creator:
    creator = Creator(
        id="c-inc-1",
        youtube_channel_id="UC_inc_1",
        channel_name="Incident Streamer",
    )
    db_session.add(creator)
    await db_session.flush()
    return creator


@pytest.mark.asyncio
async def test_incident_reporting_and_deduplication(
    db_session: AsyncSession, incident_creator: Creator
):
    event_bus = EventBus()
    service = IncidentService(db_session, event_bus=event_bus)

    # First report creates a new incident
    inc1, is_new1 = await service.report_incident(
        severity="CRITICAL",
        service="YOUTUBE",
        summary="YouTube API quota exhausted",
        creator_id=incident_creator.id,
    )
    assert is_new1 is True
    assert inc1.status == "OPEN"
    assert inc1.severity == "CRITICAL"

    # Second report on same service and creator deduplicates
    inc2, is_new2 = await service.report_incident(
        severity="CRITICAL",
        service="YOUTUBE",
        summary="Repeated 429 quota exhaustion",
        creator_id=incident_creator.id,
        action="Applied cooldown",
    )
    assert is_new2 is False
    assert inc1.id == inc2.id


@pytest.mark.asyncio
async def test_incident_lifecycle_resolution(db_session: AsyncSession, incident_creator: Creator):
    event_bus = EventBus()
    service = IncidentService(db_session, event_bus=event_bus)

    inc, _ = await service.report_incident(
        severity="HIGH",
        service="REDIS",
        summary="Redis connection pool timeout",
        creator_id=incident_creator.id,
    )

    # Mitigate
    mitigated = await service.update_status(
        inc.incident_id, "MITIGATED", action="Switched to local memory fallback"
    )
    assert mitigated is not None
    assert mitigated.status == "MITIGATED"
    assert mitigated.mitigated_at is not None

    # Resolve
    resolved = await service.update_status(
        inc.incident_id, "RESOLVED", resolution="Redis restarted and healthy"
    )
    assert resolved is not None
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at is not None

"""Unit tests for Incident state machine transitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidArgumentError
from app.services.incidents import IncidentService


@pytest.mark.asyncio
async def test_incident_legal_and_illegal_transitions(db_session: AsyncSession):
    """Verify strict transition validation on incident lifecycle."""
    svc = IncidentService(db_session)
    inc, is_new = await svc.report_incident(
        severity="WARNING",
        service="REDIS",
        summary="Redis failover active",
    )
    assert is_new is True
    assert inc.status == "OPEN"

    # Legal: OPEN -> INVESTIGATING
    inc2 = await svc.update_status(inc.incident_id, status="INVESTIGATING")
    assert inc2 is not None
    assert inc2.status == "INVESTIGATING"

    # Legal: INVESTIGATING -> MITIGATED
    inc3 = await svc.update_status(inc.incident_id, status="MITIGATED")
    assert inc3 is not None
    assert inc3.status == "MITIGATED"

    # Legal: MITIGATED -> RESOLVED
    inc4 = await svc.update_status(inc.incident_id, status="RESOLVED", resolution="Redis rebooted")
    assert inc4 is not None
    assert inc4.status == "RESOLVED"

    # Illegal: Attempting to update from RESOLVED to INVESTIGATING directly raises InvalidArgumentError
    with pytest.raises(InvalidArgumentError):
        await svc.update_status(inc.incident_id, status="INVESTIGATING")

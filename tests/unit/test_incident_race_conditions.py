"""Unit tests verifying concurrent incident reporting deduplication without race conditions."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.incidents import IncidentService


@pytest.mark.asyncio
async def test_concurrent_incident_reporting_deduplication(db_session: AsyncSession):
    """Verify that concurrent tasks reporting the same incident produce exactly one incident."""
    svc = IncidentService(db_session)

    # Launch 5 concurrent reporting tasks for the same service failure
    async def report_task(task_num: int):
        return await svc.report_incident(
            severity="CRITICAL",
            service="POSTGRES",
            summary="Connection pool exhausted",
            action=f"Worker {task_num} triggered alert",
        )

    results = await asyncio.gather(*[report_task(i) for i in range(5)])

    incidents = [r[0] for r in results]
    is_news = [r[1] for r in results]

    # Exactly one task should have created the incident (is_new=True)
    assert is_news.count(True) == 1
    assert is_news.count(False) == 4

    # All returned incidents reference the exact same incident_id
    incident_ids = {inc.incident_id for inc in incidents}
    assert len(incident_ids) == 1

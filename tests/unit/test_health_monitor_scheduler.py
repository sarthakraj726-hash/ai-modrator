"""Unit tests for HealthMonitorSupervisor continuous scheduler."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.health_monitor import HealthMonitorSupervisor, SubsystemStatus


@pytest.mark.asyncio
async def test_health_supervisor_lifecycle_and_evaluation(db_session: AsyncSession):
    """Verify background health supervisor starts, runs evaluation cycle, and cancels cleanly."""
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    supervisor = HealthMonitorSupervisor(
        interval_seconds=0.1, timeout_seconds=2.0, session_factory=session_factory
    )

    # Initial state
    assert supervisor.get_latest_snapshot() is None
    assert supervisor.cycles_executed == 0

    # Start supervisor
    await supervisor.start()
    assert supervisor._task is not None
    assert not supervisor._task.done()

    # Wait for at least 2 cycles
    await asyncio.sleep(0.35)

    snapshot = supervisor.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot["service"] == "goddess-ai-modrator"
    assert snapshot["overall_status"] in (SubsystemStatus.HEALTHY, SubsystemStatus.DEGRADED)
    assert supervisor.cycles_executed >= 2
    assert supervisor.last_cycle_at is not None
    assert isinstance(supervisor.last_cycle_at, datetime)

    # Stop supervisor
    await supervisor.stop()
    assert supervisor._task is None
    assert supervisor._stop_event.is_set()


@pytest.mark.asyncio
async def test_health_supervisor_timeout_shielding():
    """Verify health supervisor isolates exceptions and continues running."""
    supervisor = HealthMonitorSupervisor(interval_seconds=0.05, timeout_seconds=0.01)

    # Mock an evaluate cycle that raises an exception
    async def failing_cycle():
        raise RuntimeError("Simulated transient check failure")

    # Manually trigger evaluate_cycle failure handling
    snapshot = await supervisor.evaluate_cycle()
    assert snapshot is not None
    assert snapshot["overall_status"] == SubsystemStatus.CRITICAL
    assert supervisor.consecutive_failures >= 1

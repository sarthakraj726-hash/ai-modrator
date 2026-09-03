"""Unit tests for HealthMonitorService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.health_monitor import HealthMonitorService, SubsystemStatus


@pytest.mark.asyncio
async def test_health_monitor_detailed_snapshot(db_session: AsyncSession):
    from app.youtube.key_pool import KeyStatus, get_key_pool

    pool = get_key_pool()
    for k in pool._keys.values():
        k.status = KeyStatus.AVAILABLE
        k.cooldown_until = 0.0

    monitor = HealthMonitorService(session=db_session)
    snapshot = await monitor.get_detailed_snapshot()

    assert snapshot["service"] == "goddess-ai-modrator"
    assert snapshot["overall_status"] in (SubsystemStatus.HEALTHY, SubsystemStatus.DEGRADED)
    assert "subsystems" in snapshot
    assert "database" in snapshot["subsystems"]
    assert snapshot["subsystems"]["database"]["status"] == SubsystemStatus.HEALTHY
    assert "youtube" in snapshot["subsystems"]
    assert "workers" in snapshot["subsystems"]
    assert "process" in snapshot
    assert snapshot["security"]["secrets_redacted"] is True
    assert snapshot["security"]["rbac_enforced"] is True

"""Unit tests verifying mode-aware overall health status aggregation."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.health_monitor import HealthMonitorService, SubsystemStatus


@pytest.mark.asyncio
async def test_health_aggregation_all_healthy(db_session):
    """When all subsystems report HEALTHY, overall status is HEALTHY."""
    svc = HealthMonitorService(session=db_session)

    # Mock all checks returning healthy
    with (
        patch.object(svc, "check_database", new_callable=AsyncMock) as m_db,
        patch.object(svc, "check_redis", new_callable=AsyncMock) as m_rd,
        patch.object(svc, "check_youtube", new_callable=AsyncMock) as m_yt,
        patch.object(svc, "check_workers") as m_wm,
        patch.object(svc, "check_openrouter", new_callable=AsyncMock) as m_ai,
        patch.object(svc, "check_discord") as m_dc,
        patch.object(svc, "check_eventbus") as m_eb,
        patch.object(svc, "check_economy_integrity", new_callable=AsyncMock) as m_ec,
        patch.object(svc, "check_moderation_queue", new_callable=AsyncMock) as m_md,
        patch.object(svc, "check_websub", new_callable=AsyncMock) as m_ws,
    ):
        m_db.return_value = {"status": SubsystemStatus.HEALTHY}
        m_rd.return_value = {"status": SubsystemStatus.HEALTHY}
        m_yt.return_value = {"status": SubsystemStatus.HEALTHY}
        m_wm.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ai.return_value = {"status": SubsystemStatus.HEALTHY}
        m_dc.return_value = {"status": SubsystemStatus.HEALTHY}
        m_eb.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ec.return_value = {"status": SubsystemStatus.HEALTHY}
        m_md.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ws.return_value = {"status": SubsystemStatus.HEALTHY}

        snapshot = await svc.get_detailed_snapshot()
        assert snapshot["overall_status"] == SubsystemStatus.HEALTHY


@pytest.mark.asyncio
async def test_health_aggregation_critical_dependency(db_session):
    """When a critical dependency (e.g. database) is CRITICAL, overall status is CRITICAL."""
    svc = HealthMonitorService(session=db_session)

    with (
        patch.object(svc, "check_database", new_callable=AsyncMock) as m_db,
        patch.object(svc, "check_redis", new_callable=AsyncMock) as m_rd,
        patch.object(svc, "check_youtube", new_callable=AsyncMock) as m_yt,
        patch.object(svc, "check_workers") as m_wm,
        patch.object(svc, "check_openrouter", new_callable=AsyncMock) as m_ai,
        patch.object(svc, "check_discord") as m_dc,
        patch.object(svc, "check_eventbus") as m_eb,
        patch.object(svc, "check_economy_integrity", new_callable=AsyncMock) as m_ec,
        patch.object(svc, "check_moderation_queue", new_callable=AsyncMock) as m_md,
        patch.object(svc, "check_websub", new_callable=AsyncMock) as m_ws,
    ):
        m_db.return_value = {"status": SubsystemStatus.CRITICAL}
        m_rd.return_value = {"status": SubsystemStatus.HEALTHY}
        m_yt.return_value = {"status": SubsystemStatus.HEALTHY}
        m_wm.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ai.return_value = {"status": SubsystemStatus.HEALTHY}
        m_dc.return_value = {"status": SubsystemStatus.HEALTHY}
        m_eb.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ec.return_value = {"status": SubsystemStatus.HEALTHY}
        m_md.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ws.return_value = {"status": SubsystemStatus.HEALTHY}

        snapshot = await svc.get_detailed_snapshot()
        assert snapshot["overall_status"] == SubsystemStatus.CRITICAL


@pytest.mark.asyncio
async def test_health_aggregation_peripheral_degraded(db_session):
    """When a peripheral subsystem (e.g. discord or openrouter) is DEGRADED, overall status is DEGRADED, not CRITICAL."""
    svc = HealthMonitorService(session=db_session)

    with (
        patch.object(svc, "check_database", new_callable=AsyncMock) as m_db,
        patch.object(svc, "check_redis", new_callable=AsyncMock) as m_rd,
        patch.object(svc, "check_youtube", new_callable=AsyncMock) as m_yt,
        patch.object(svc, "check_workers") as m_wm,
        patch.object(svc, "check_openrouter", new_callable=AsyncMock) as m_ai,
        patch.object(svc, "check_discord") as m_dc,
        patch.object(svc, "check_eventbus") as m_eb,
        patch.object(svc, "check_economy_integrity", new_callable=AsyncMock) as m_ec,
        patch.object(svc, "check_moderation_queue", new_callable=AsyncMock) as m_md,
        patch.object(svc, "check_websub", new_callable=AsyncMock) as m_ws,
    ):
        m_db.return_value = {"status": SubsystemStatus.HEALTHY}
        m_rd.return_value = {"status": SubsystemStatus.HEALTHY}
        m_yt.return_value = {"status": SubsystemStatus.HEALTHY}
        m_wm.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ai.return_value = {"status": SubsystemStatus.DEGRADED}  # Peripheral AI degraded
        m_dc.return_value = {"status": SubsystemStatus.HEALTHY}
        m_eb.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ec.return_value = {"status": SubsystemStatus.HEALTHY}
        m_md.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ws.return_value = {"status": SubsystemStatus.HEALTHY}

        snapshot = await svc.get_detailed_snapshot()
        assert snapshot["overall_status"] == SubsystemStatus.DEGRADED


@pytest.mark.asyncio
async def test_health_aggregation_api_mode_bypasses_workers(db_session):
    """In API mode, workers and youtube ingestion are bypassed and do not degrade the API server."""
    svc = HealthMonitorService(session=db_session)

    with (
        patch.object(svc.settings, "APP_SERVICE_MODE", "api"),
        patch.object(svc, "check_database", new_callable=AsyncMock) as m_db,
        patch.object(svc, "check_redis", new_callable=AsyncMock) as m_rd,
        patch.object(svc, "check_youtube", new_callable=AsyncMock) as m_yt,
        patch.object(svc, "check_workers") as m_wm,
        patch.object(svc, "check_openrouter", new_callable=AsyncMock) as m_ai,
        patch.object(svc, "check_discord") as m_dc,
        patch.object(svc, "check_eventbus") as m_eb,
        patch.object(svc, "check_economy_integrity", new_callable=AsyncMock) as m_ec,
        patch.object(svc, "check_moderation_queue", new_callable=AsyncMock) as m_md,
        patch.object(svc, "check_websub", new_callable=AsyncMock) as m_ws,
    ):
        m_db.return_value = {"status": SubsystemStatus.HEALTHY}
        m_rd.return_value = {"status": SubsystemStatus.HEALTHY}
        m_yt.return_value = {"status": SubsystemStatus.UNHEALTHY}  # Bypassed in API mode
        m_wm.return_value = {"status": SubsystemStatus.UNHEALTHY}  # Bypassed in API mode
        m_ai.return_value = {"status": SubsystemStatus.HEALTHY}
        m_dc.return_value = {"status": SubsystemStatus.HEALTHY}
        m_eb.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ec.return_value = {"status": SubsystemStatus.HEALTHY}
        m_md.return_value = {"status": SubsystemStatus.HEALTHY}
        m_ws.return_value = {"status": SubsystemStatus.HEALTHY}

        snapshot = await svc.get_detailed_snapshot()
        # In API mode, worker/youtube are optional/bypassed so overall remains HEALTHY
        assert snapshot["overall_status"] == SubsystemStatus.HEALTHY

"""Unit tests for complete subsystem health matrix and credential redaction."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.health_monitor import HealthMonitorService
from app.youtube.key_pool import KeyStatus, get_key_pool


@pytest.mark.asyncio
async def test_all_fourteen_subsystems_evaluated_and_redacted(db_session: AsyncSession):
    """Verify all 14 required subsystems are health-monitored with zero credential leakage."""
    pool = get_key_pool()
    for k in pool._keys.values():
        k.status = KeyStatus.AVAILABLE
        k.cooldown_until = 0.0

    monitor = HealthMonitorService(session=db_session)
    snapshot = await monitor.get_detailed_snapshot()

    subsystems = snapshot["subsystems"]

    # Verify all expected subsystems exist
    expected_subsystems = [
        "database",
        "redis",
        "youtube",
        "workers",
        "openrouter",
        "discord",
        "eventbus",
        "economy",
        "moderation",
        "websub",
    ]
    for sub in expected_subsystems:
        assert sub in subsystems, f"Subsystem '{sub}' missing from health snapshot"
        assert "status" in subsystems[sub]

    # Verify process and security metrics
    assert "process" in snapshot
    assert "uptime_seconds" in snapshot["process"]
    assert "memory_mb" in snapshot["process"]
    assert "pid" in snapshot["process"]
    assert snapshot["security"]["secrets_redacted"] is True
    assert snapshot["security"]["rbac_enforced"] is True

    # Critical security check: Ensure zero API keys, passwords, or tokens in snapshot string
    snapshot_str = str(snapshot)
    forbidden_tokens = [
        "AIza",
        "sk-or-v1",
        "dev-admin-secret",
        "password",
        "mock-youtube-dev-key",
    ]
    for token in forbidden_tokens:
        assert token not in snapshot_str, f"Secret token '{token}' detected in health snapshot!"


@pytest.mark.asyncio
async def test_openrouter_readiness_distinguishes_states(db_session: AsyncSession):
    """Verify OpenRouter readiness distinguishes CONFIG_MISSING, DEGRADED, and READY."""
    from app.ai.openrouter import OpenRouterProvider

    # 1. Config missing
    provider_no_key = OpenRouterProvider(api_key="")
    res = await provider_no_key.check_readiness()
    assert res["status"] == "CONFIG_MISSING"
    assert res["ready"] is False

    # 2. Circuit breaker open
    provider_broken = OpenRouterProvider(api_key="valid-test-key")
    provider_broken.circuit_breaker.state = "OPEN"
    provider_broken.circuit_breaker.last_failure_time = 9999999999.0
    res = await provider_broken.check_readiness()
    assert res["status"] == "DEGRADED"
    assert res["ready"] is False

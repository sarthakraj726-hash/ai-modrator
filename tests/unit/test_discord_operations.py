"""Unit tests for DiscordOperationsService."""

import pytest

from app.discord.operations import DiscordAlertPriority, DiscordOperationsService


@pytest.mark.asyncio
async def test_critical_alert_bypasses_cooldown():
    service = DiscordOperationsService(dev_channel_id="dev-12345", alert_cooldown_seconds=300)

    # First critical alert
    res1 = await service.send_critical_incident_alert(
        incident_id="INC-001",
        service="ECONOMY",
        summary="Ledger imbalance detected",
        severity=DiscordAlertPriority.CRITICAL,
    )
    assert res1 is True

    # Immediate second critical alert must NOT be suppressed
    res2 = await service.send_critical_incident_alert(
        incident_id="INC-001",
        service="ECONOMY",
        summary="Ledger imbalance detected",
        severity=DiscordAlertPriority.CRITICAL,
    )
    assert res2 is True


@pytest.mark.asyncio
async def test_non_critical_alert_cooldown_suppression():
    service = DiscordOperationsService(dev_channel_id="dev-12345", alert_cooldown_seconds=300)

    # First warning alert
    res1 = await service.send_critical_incident_alert(
        incident_id="INC-002",
        service="REDIS",
        summary="High memory warning",
        severity=DiscordAlertPriority.WARNING,
    )
    assert res1 is True

    # Immediate repeated warning alert is suppressed by cooldown
    should_suppress = service._should_suppress_alert(
        "REDIS:WARNING:High memory warning", DiscordAlertPriority.WARNING
    )
    assert should_suppress is True


@pytest.mark.asyncio
async def test_stream_and_daily_summary_formatting():
    service = DiscordOperationsService(dev_channel_id="dev-12345")

    # Stream summary
    stats = {
        "messages": 5420,
        "peak_viewers": 350,
        "moderation_deletes": 12,
        "moderation_timeouts": 2,
        "moderation_reviews": 5,
        "ai_replies": 84,
        "ai_tokens": 12400,
        "ai_fallbacks": 0,
        "xp_awarded": 18200,
        "coins_minted": 9100,
        "games_won": 15,
        "store_purchases": 8,
    }
    res_stream = await service.send_stream_summary(
        creator_id="c-1",
        stream_id="s-1",
        duration_minutes=185.0,
        stats=stats,
    )
    assert res_stream is True

    # Daily summary
    daily_stats = {
        "total_streams": 7,
        "stream_hours": 24.5,
        "messages": 35400,
        "moderation_events": 45,
        "ai_tokens": 85000,
        "quota_used": 2400,
        "active_incidents": 0,
        "ledger_status": "BALANCED",
    }
    res_daily = await service.send_daily_system_summary(daily_stats)
    assert res_daily is True

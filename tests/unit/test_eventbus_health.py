"""Unit tests for EventBus honest health and telemetry reporting."""

from unittest.mock import MagicMock, patch

import pytest

from app.events.bus import EventBus


@pytest.mark.asyncio
async def test_eventbus_health_in_unified_mode():
    """In unified mode, EventBus uses in-process local dispatch and is always HEALTHY."""
    with patch("app.events.bus.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.is_unified_service = True
        mock_settings.return_value = settings_instance

        bus = EventBus()
        health = bus.get_health()

        assert health["status"] == "HEALTHY"
        assert health["mode"] == "UNIFIED"
        assert health["transport_available"] is True
        assert health["listener_active"] is False


@pytest.mark.asyncio
async def test_eventbus_health_in_decoupled_mode_healthy():
    """In decoupled mode with active listener and real transport, reports HEALTHY."""
    with (
        patch("app.events.bus.get_settings") as mock_settings,
        patch("app.cache.redis.get_redis_sync") as mock_get_redis,
    ):
        settings_instance = MagicMock()
        settings_instance.is_unified_service = False
        mock_settings.return_value = settings_instance

        # Real Redis (not fallback)
        mock_redis = MagicMock()
        mock_redis._is_fallback = False
        mock_get_redis.return_value = mock_redis

        bus = EventBus()
        # Mock active listener task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bus._listener_task = mock_task
        bus.consecutive_listener_failures = 0

        health = bus.get_health()
        assert health["status"] == "HEALTHY"
        assert health["mode"] == "DECOUPLED"
        assert health["transport_available"] is True
        assert health["listener_active"] is True


@pytest.mark.asyncio
async def test_eventbus_health_in_decoupled_mode_listener_stopped():
    """In decoupled mode, if listener task is stopped/missing, reports UNHEALTHY."""
    with (
        patch("app.events.bus.get_settings") as mock_settings,
        patch("app.cache.redis.get_redis_sync") as mock_get_redis,
    ):
        settings_instance = MagicMock()
        settings_instance.is_unified_service = False
        mock_settings.return_value = settings_instance

        mock_redis = MagicMock()
        mock_redis._is_fallback = False
        mock_get_redis.return_value = mock_redis

        bus = EventBus()
        bus._listener_task = None  # Listener not running

        health = bus.get_health()
        assert health["status"] in ("UNHEALTHY", "DEGRADED")
        assert health["listener_active"] is False


@pytest.mark.asyncio
async def test_eventbus_health_in_decoupled_mode_redis_fallback():
    """In decoupled mode, if Redis is down (fallback active), reports DEGRADED/UNHEALTHY."""
    with (
        patch("app.events.bus.get_settings") as mock_settings,
        patch("app.cache.redis.get_redis_sync") as mock_get_redis,
    ):
        settings_instance = MagicMock()
        settings_instance.is_unified_service = False
        mock_settings.return_value = settings_instance

        # In-memory fallback
        mock_fallback = MagicMock()
        mock_fallback._is_fallback = True
        mock_get_redis.return_value = mock_fallback

        bus = EventBus()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bus._listener_task = mock_task

        health = bus.get_health()
        assert health["status"] in ("DEGRADED", "UNHEALTHY")
        assert health["transport_available"] is False


@pytest.mark.asyncio
async def test_eventbus_health_listener_recovery():
    """Verify health transitions from DEGRADED back to HEALTHY upon listener recovery."""
    with (
        patch("app.events.bus.get_settings") as mock_settings,
        patch("app.cache.redis.get_redis_sync") as mock_get_redis,
    ):
        settings_instance = MagicMock()
        settings_instance.is_unified_service = False
        mock_settings.return_value = settings_instance

        mock_redis = MagicMock()
        mock_redis._is_fallback = False
        mock_get_redis.return_value = mock_redis

        bus = EventBus()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bus._listener_task = mock_task

        # In failure state
        bus.consecutive_listener_failures = 4
        assert bus.get_health()["status"] == "DEGRADED"

        # Recovered
        bus.consecutive_listener_failures = 0
        assert bus.get_health()["status"] == "HEALTHY"

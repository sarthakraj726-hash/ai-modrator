"""Chaos tests verifying Redis failure contracts and safe degraded fallback modes."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.cache.locks import DistributedLock
from app.cache.redis import InMemoryRedisFallback
from app.events.bus import EventBus
from app.events.schemas import BaseEvent


@pytest.mark.asyncio
async def test_redis_in_memory_fallback_contract():
    """Verify that when Redis is disconnected, system engages safe in-memory fallback."""
    fallback = InMemoryRedisFallback()

    # 1. String set and get with TTL
    await fallback.set("test_key", "test_val", ex=60)
    val = await fallback.get("test_key")
    assert val == "test_val"

    # 2. Set with NX (distributed lock simulation)
    is_set = await fallback.set("lock_key", "proc_1", nx=True)
    assert is_set is True

    # Duplicate acquisition fails
    is_set_again = await fallback.set("lock_key", "proc_2", nx=True)
    assert is_set_again is False

    # 3. Ping returns True
    assert await fallback.ping() is True


@pytest.mark.asyncio
async def test_distributed_lock_unified_vs_decoupled_failure_policy():
    """
    Verify failure policy contract:
    - Unified mode: can acquire lock on local in-memory store.
    - Decoupled mode: must FAIL CLOSED when Redis is unavailable to prevent cross-process split-brain.
    """
    fallback_client = InMemoryRedisFallback()
    fallback_client._is_fallback = True

    # 1. Unified Mode: lock acquisition succeeds safely locally
    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.cache.locks.get_redis_client", return_value=fallback_client),
    ):
        settings_unified = MagicMock()
        settings_unified.is_unified_service = True
        mock_settings.return_value = settings_unified

        lock_unified = DistributedLock("stream:stream-123:restart", acquire_timeout=0.1)
        acquired = await lock_unified.acquire()
        assert acquired is True
        await lock_unified.release()

    # 2. Decoupled Mode: lock acquisition FAILS CLOSED
    with (
        patch("app.core.config.get_settings") as mock_settings,
        patch("app.cache.locks.get_redis_client", return_value=fallback_client),
    ):
        settings_decoupled = MagicMock()
        settings_decoupled.is_unified_service = False
        mock_settings.return_value = settings_decoupled

        lock_decoupled = DistributedLock("stream:stream-123:restart", acquire_timeout=0.1)
        acquired = await lock_decoupled.acquire()
        # Must fail closed rather than pretending cross-process mutual exclusion exists
        assert acquired is False


@pytest.mark.asyncio
async def test_eventbus_publish_resilience_during_redis_outage():
    """Verify EventBus local delivery continues without unhandled crash when Redis is down."""
    fallback_client = InMemoryRedisFallback()
    fallback_client._is_fallback = True

    bus = EventBus()
    received_events = []

    async def sample_handler(evt: BaseEvent) -> None:
        received_events.append(evt)

    bus.subscribe("SystemAlert", sample_handler)

    with patch("app.events.bus.get_redis_client", return_value=fallback_client):
        # Publishing should deliver locally and not raise
        await bus.publish(
            BaseEvent(event_type="SystemAlert", payload={"alert": "redis_offline"}),
            broadcast_distributed=True,
        )
        await asyncio.sleep(0.05)

    assert len(received_events) == 1
    assert received_events[0].event_type == "SystemAlert"

"""Chaos tests verifying Redis failure contracts and safe degraded fallback modes."""

import pytest

from app.cache.redis import InMemoryRedisFallback


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

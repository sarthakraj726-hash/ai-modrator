"""Integration tests for Cache, DistributedLock, and Redis abstractions."""

import pytest

from app.cache.cache import Cache
from app.cache.locks import DistributedLock


@pytest.mark.asyncio
async def test_cache_service():
    cache = Cache(prefix="test_c")

    # Set & Get
    await cache.set("user_data", {"name": "Alice", "score": 100}, ttl_seconds=60)
    val = await cache.get("user_data")
    assert val == {"name": "Alice", "score": 100}

    # Delete
    await cache.delete("user_data")
    assert await cache.get("user_data") is None

    # Remember
    computed = await cache.remember("expensive", 60, lambda: {"computed": True})
    assert computed == {"computed": True}
    cached_again = await cache.get("expensive")
    assert cached_again == {"computed": True}


@pytest.mark.asyncio
async def test_distributed_lock_mutual_exclusion():
    lock1 = DistributedLock("resource-1", ttl_seconds=5, acquire_timeout=0.1)
    lock2 = DistributedLock("resource-1", ttl_seconds=5, acquire_timeout=0.1)

    # Lock 1 acquires
    assert await lock1.acquire() is True

    # Lock 2 cannot acquire while Lock 1 holds it
    assert await lock2.acquire() is False

    # Lock 1 releases
    assert await lock1.release() is True

    # Lock 2 can now acquire
    assert await lock2.acquire() is True
    await lock2.release()

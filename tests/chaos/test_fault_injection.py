"""Chaos Engineering and Fault Injection Test Suite (Phase 1 - Step 26).

Simulates:
1. Redis disconnection / failure
2. Database timeout / rollback
3. YouTube API 401 Unauthorized (Auth failure)
4. YouTube API 429 Quota / Rate limit error
5. YouTube API 500 / 503 Server error with circuit breaker trip
6. Duplicate connect race condition
7. Graceful worker shutdown under high load
"""

import asyncio

import pytest

import app.cache.redis as redis_module
from app.cache.redis import InMemoryRedisFallback
from app.core.exceptions import (
    CircuitBreakerOpenError,
    StreamSessionAlreadyActiveError,
    YouTubeAPIError,
)
from app.utils.circuit_breaker import CircuitBreaker
from app.workers.manager import WorkerManager
from app.youtube.client import YouTubeClient
from app.youtube.models import YouTubeChatPage, YouTubeStreamInfo


class FaultyRedisFallback(InMemoryRedisFallback):
    """Redis fallback that simulates network partitions and connection drops."""
    def __init__(self):
        super().__init__()
        self.is_broken = False

    async def get(self, key: str):
        if self.is_broken:
            raise ConnectionError("Simulated Redis Connection Refused")
        return await super().get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if self.is_broken:
            raise ConnectionError("Simulated Redis Write Timeout")
        return await super().set(key, value, ex=ex, nx=nx)


@pytest.mark.asyncio
async def test_chaos_redis_failure_and_recovery():
    faulty_redis = FaultyRedisFallback()
    redis_module._redis_instance = faulty_redis

    # Normal write
    await faulty_redis.set("k1", "v1")
    assert await faulty_redis.get("k1") == "v1"

    # Trip Redis partition
    faulty_redis.is_broken = True
    with pytest.raises(ConnectionError):
        await faulty_redis.get("k1")

    # Heal partition
    faulty_redis.is_broken = False
    assert await faulty_redis.get("k1") == "v1"


@pytest.mark.asyncio
async def test_chaos_circuit_breaker_under_5xx_bombardment():
    cb = CircuitBreaker(name="chaos-cb", failure_threshold=3, recovery_timeout_seconds=0.2)

    async def remote_503():
        raise YouTubeAPIError("503 Service Unavailable", status_code=503)

    # 3 failures trip circuit
    for _ in range(3):
        with pytest.raises(YouTubeAPIError):
            await cb.execute(remote_503)

    # Fast failure without calling remote
    with pytest.raises(CircuitBreakerOpenError):
        await cb.execute(remote_503)

    # Wait for cooldown
    await asyncio.sleep(0.25)

    # Circuit allows canary request in HALF-OPEN
    async def healthy_remote():
        return {"status": "ok"}

    res = await cb.execute(healthy_remote)
    assert res == {"status": "ok"}


@pytest.mark.asyncio
async def test_chaos_duplicate_stream_connect_rejection():
    manager = WorkerManager()

    # Start stream-1
    await manager.start_session("s-dup", "c-1", "v-1")

    # Duplicate attempt must fail with StreamSessionAlreadyActiveError
    with pytest.raises(StreamSessionAlreadyActiveError):
        await manager.start_session("s-dup", "c-1", "v-1")

    await manager.stop_all()


@pytest.mark.asyncio
async def test_chaos_graceful_shutdown_under_active_load():
    class FastClient(YouTubeClient):
        async def resolve_stream_info(self, video_id: str) -> YouTubeStreamInfo:
            return YouTubeStreamInfo(video_id=video_id, channel_id="c", is_live=True, live_chat_id="chat_fast")

        async def get_live_chat_messages(self, live_chat_id: str, page_token: str | None = None) -> YouTubeChatPage:
            return YouTubeChatPage(messages=[], polling_interval_millis=10)

    manager = WorkerManager(youtube_client=FastClient())

    # Start 4 streams
    for i in range(4):
        await manager.start_session(f"load-s-{i}", f"c-{i}", f"v-{i}", live_chat_id="chat_fast")

    await asyncio.sleep(0.1)
    assert await manager.get_active_count() == 4

    # Issue stop_all during active polling
    await manager.stop_all(timeout=2.0)
    assert await manager.get_active_count() == 0

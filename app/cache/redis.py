"""Redis client connection wrapper and in-memory mock fallback."""

import asyncio
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.cache.redis")

RedisClient = Any


class InMemoryRedisFallback:
    """In-memory Redis replacement for testing and local fallback."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._expirations: dict[str, float] = {}
        self._pubsub_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def _cleanup_expired(self, key: str) -> None:
        if key in self._expirations and time.time() > self._expirations[key]:
            self._store.pop(key, None)
            self._expirations.pop(key, None)

    async def get(self, key: str) -> str | None:
        async with self._lock:
            self._cleanup_expired(key)
            return self._store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        ttl: int | None = None,
        nx: bool = False,
    ) -> bool:
        async with self._lock:
            self._cleanup_expired(key)
            if nx and key in self._store:
                return False
            self._store[key] = str(value)
            expiry = ex if ex is not None else ttl
            if expiry:
                self._expirations[key] = time.time() + expiry
            else:
                self._expirations.pop(key, None)
            return True

    async def incrby(self, key: str, amount: int = 1) -> int:
        async with self._lock:
            self._cleanup_expired(key)
            current = int(self._store.get(key, 0))
            new_val = current + amount
            self._store[key] = str(new_val)
            return new_val

    async def incr(self, key: str) -> int:
        return await self.incrby(key, 1)

    async def decr(self, key: str) -> int:
        return await self.decrby(key, 1)

    async def decrby(self, key: str, amount: int = 1) -> int:
        return await self.incrby(key, -amount)

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            count = 0
            for k in keys:
                if k in self._store:
                    self._store.pop(k, None)
                    self._expirations.pop(k, None)
                    count += 1
            return count

    async def expire(self, key: str, seconds: int) -> bool:
        async with self._lock:
            if key in self._store:
                self._expirations[key] = time.time() + seconds
                return True
            return False

    async def ttl(self, key: str) -> int:
        async with self._lock:
            self._cleanup_expired(key)
            if key not in self._store:
                return -2
            if key in self._expirations:
                return max(0, int(self._expirations[key] - time.time()))
            return -1

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        async with self._lock:
            self._store.clear()
            self._expirations.clear()


_redis_instance: Any = None


async def get_redis_client() -> Any:
    """Return the global Redis client or fallback."""
    global _redis_instance
    if _redis_instance is None:
        await init_redis()
    return _redis_instance


def get_redis_sync() -> Any:
    """Synchronous accessor for Redis client or InMemoryFallback."""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = InMemoryRedisFallback()
    return _redis_instance


async def init_redis() -> Any:
    """Initialize Redis connection or fallback to in-memory store."""
    global _redis_instance
    settings = get_settings()

    if settings.is_testing:
        logger.info("Initializing in-memory Redis fallback (testing mode)")
        _redis_instance = InMemoryRedisFallback()
        return _redis_instance

    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
        await client.ping()
        _redis_instance = client
        logger.info(f"Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(f"Could not connect to Redis ({e}). Falling back to InMemoryRedisFallback.")
        _redis_instance = InMemoryRedisFallback()
    return _redis_instance


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_instance
    if _redis_instance is not None:
        if hasattr(_redis_instance, "aclose"):
            await _redis_instance.aclose()
        elif hasattr(_redis_instance, "close"):
            await _redis_instance.close()
        _redis_instance = None

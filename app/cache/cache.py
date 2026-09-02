"""Cache service abstraction with serialization and cache-aside helpers."""

import asyncio
import json
from collections.abc import Callable
from typing import Any, TypeVar

from app.cache.redis import get_redis_client
from app.core.logging import get_logger

logger = get_logger("app.cache")

T = TypeVar("T")


class Cache:
    """High-level caching service wrapping Redis."""

    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix

    def _format_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Retrieve and deserialize value from cache."""
        redis = await get_redis_client()
        raw = await redis.get(self._format_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Serialize and store value in cache with TTL."""
        redis = await get_redis_client()
        formatted_key = self._format_key(key)
        serialized = json.dumps(value) if not isinstance(value, str) else value
        return bool(await redis.set(formatted_key, serialized, ex=ttl_seconds))

    async def delete(self, key: str) -> bool:
        """Remove key from cache."""
        redis = await get_redis_client()
        return bool(await redis.delete(self._format_key(key)))

    async def remember(self, key: str, ttl_seconds: int, factory: Callable[[], Any]) -> Any:
        """Cache-aside pattern: return cached value or compute, cache, and return."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value (handling both async and sync factories)
        if asyncio.iscoroutinefunction(factory):
            computed = await factory()
        else:
            computed = factory()

        await self.set(key, computed, ttl_seconds=ttl_seconds)
        return computed

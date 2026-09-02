"""Sliding window rate limiter using Redis / in-memory fallback."""

import time

from app.cache.redis import get_redis_client
from app.core.exceptions import RateLimitExceededError
from app.core.logging import get_logger

logger = get_logger("app.cache.rate_limiter")


class RateLimiter:
    """
    Fixed / sliding-window counter rate limiter.
    """

    def __init__(self, key_prefix: str = "rate_limit"):
        self.key_prefix = key_prefix

    def _get_key(self, identifier: str, window_seconds: int) -> str:
        current_window = int(time.time() // window_seconds)
        return f"{self.key_prefix}:{identifier}:{current_window}"

    async def is_allowed(
        self, identifier: str, max_requests: int, window_seconds: int = 60
    ) -> bool:
        """Check whether request is allowed within rate limit window."""
        redis = await get_redis_client()
        key = self._get_key(identifier, window_seconds)

        current = await redis.incrby(key, 1)
        if current == 1:
            # Set TTL slightly longer than window to ensure cleanup
            await redis.expire(key, window_seconds + 5)

        return current <= max_requests

    async def check(self, identifier: str, max_requests: int, window_seconds: int = 60) -> None:
        """Enforce rate limit, raising RateLimitExceededError if limit is breached."""
        allowed = await self.is_allowed(identifier, max_requests, window_seconds)
        if not allowed:
            raise RateLimitExceededError(retry_after_seconds=window_seconds)

    async def get_remaining(
        self, identifier: str, max_requests: int, window_seconds: int = 60
    ) -> int:
        """Return the number of remaining allowed requests in current window."""
        redis = await get_redis_client()
        key = self._get_key(identifier, window_seconds)
        val = await redis.get(key)
        used = int(val) if val else 0
        return max(0, max_requests - used)

"""Distributed lock implementation using Redis with TTL and auto-release."""

import asyncio
import uuid
from typing import Any

from app.cache.redis import get_redis_client
from app.core.exceptions import LockAcquisitionError
from app.core.logging import get_logger

logger = get_logger("app.cache.locks")


class DistributedLock:
    """
    Distributed mutual exclusion lock based on Redis SET NX EX.
    Guarantees only the holding token can release the lock.
    """

    def __init__(
        self,
        lock_name: str,
        ttl_seconds: int = 30,
        acquire_timeout: float = 10.0,
        retry_interval: float = 0.1,
    ):
        self.lock_name = f"lock:{lock_name}"
        self.ttl_seconds = ttl_seconds
        self.acquire_timeout = acquire_timeout
        self.retry_interval = retry_interval
        self.token = str(uuid.uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        """Attempt to acquire the lock before timeout."""
        from app.core.config import get_settings

        settings = get_settings()
        redis = await get_redis_client()
        is_fallback = getattr(redis, "_is_fallback", False)

        # In decoupled/distributed mode, fail closed if Redis is unavailable to prevent duplicate workers
        if not settings.is_unified_service and is_fallback:
            logger.error(
                f"DistributedLock '{self.lock_name}' rejected: "
                "Redis transport unavailable in DECOUPLED mode. Failing closed to prevent split-brain."
            )
            return False

        deadline = asyncio.get_event_loop().time() + self.acquire_timeout

        while asyncio.get_event_loop().time() < deadline:
            acquired = await redis.set(
                self.lock_name,
                self.token,
                ex=self.ttl_seconds,
                nx=True,
            )
            if acquired:
                self._acquired = True
                return True
            await asyncio.sleep(self.retry_interval)

        return False

    async def release(self) -> bool:
        """Release the lock if and only if owned by this instance's token."""
        if not self._acquired:
            return False

        redis = await get_redis_client()
        current_val = await redis.get(self.lock_name)
        if current_val == self.token:
            await redis.delete(self.lock_name)
            self._acquired = False
            return True
        return False

    async def __aenter__(self) -> "DistributedLock":
        acquired = await self.acquire()
        if not acquired:
            raise LockAcquisitionError(self.lock_name)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.release()

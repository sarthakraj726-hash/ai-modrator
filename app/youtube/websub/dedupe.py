"""Distributed WebSub notification deduplicator."""

from app.cache.redis import get_redis_client
from app.core.logging import get_logger

logger = get_logger("app.youtube.websub.dedupe")


class WebSubDeduplicator:
    """
    Ensures WebSub notifications are processed exactly once within a configurable TTL window.
    Even if Google sends 10 duplicate delivery retries, only 1 effective discovery event is emitted.
    """

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self.ttl_seconds = ttl_seconds

    async def is_duplicate_or_record(self, dedupe_hash: str) -> bool:
        """
        Check if notification hash was already seen.
        If new, records it and returns False (not duplicate).
        If already seen, returns True (is duplicate).
        """
        redis = await get_redis_client()
        key = f"websub:dedupe:{dedupe_hash}"
        # Use SET with NX to atomically acquire dedupe lock
        acquired = await redis.set(key, "1", ex=self.ttl_seconds, nx=True)
        if acquired:
            logger.debug(f"WebSub notification {dedupe_hash[:8]} recorded as NEW.")
            return False

        logger.info(f"WebSub notification {dedupe_hash[:8]} identified as DUPLICATE. Suppressing.")
        return True


_global_websub_deduplicator: WebSubDeduplicator | None = None


def get_websub_deduplicator() -> WebSubDeduplicator:
    """Return singleton WebSubDeduplicator."""
    global _global_websub_deduplicator
    if _global_websub_deduplicator is None:
        _global_websub_deduplicator = WebSubDeduplicator()
    return _global_websub_deduplicator

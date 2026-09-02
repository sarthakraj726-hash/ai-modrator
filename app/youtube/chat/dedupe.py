"""Redis-backed live chat message deduplication."""

from app.cache.redis import get_redis_client
from app.core.logging import get_logger

logger = get_logger("app.youtube.chat.dedupe")


class ChatDeduplicator:
    """
    Ensures that identical YouTube live chat messages are processed exactly once.
    Uses message_id as primary deduplication key with a configurable sliding TTL window.
    """

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds

    async def is_duplicate_or_record(self, message_id: str) -> bool:
        """
        Check if message_id was already seen.
        Returns False if new (recorded), True if duplicate.
        """
        if not message_id:
            return False

        redis = await get_redis_client()
        key = f"chat:dedupe:{message_id}"
        # Atomic set with NX and expiration
        is_new = await redis.set(key, "1", ex=self.ttl_seconds, nx=True)
        if is_new:
            return False

        logger.debug(f"Chat message '{message_id}' identified as DUPLICATE. Suppressing.")
        return True


_global_chat_deduplicator: ChatDeduplicator | None = None


def get_chat_deduplicator() -> ChatDeduplicator:
    """Return singleton ChatDeduplicator."""
    global _global_chat_deduplicator
    if _global_chat_deduplicator is None:
        _global_chat_deduplicator = ChatDeduplicator()
    return _global_chat_deduplicator

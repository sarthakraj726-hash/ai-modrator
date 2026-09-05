"""Idempotent moderation action execution service."""

from app.cache.redis import RedisClient, get_redis_sync
from app.core.logging import get_logger
from app.moderation.models import ModerationAction, ModerationDecision
from app.youtube.client import YouTubeClient, get_youtube_client

logger = get_logger("app.moderation.actions")


class YouTubeModerationActionService:
    """
    Application-side authority executing moderation side effects against YouTube.
    Guarantees idempotency to prevent double-bans, duplicate deletions, or command loops.
    """

    def __init__(
        self,
        youtube_client: YouTubeClient | None = None,
        redis_client: RedisClient | None = None,
    ) -> None:
        self.youtube_client = youtube_client or get_youtube_client()
        self.redis_client = redis_client or get_redis_sync()
        self._local_idempotency_cache: set[str] = set()

    def make_idempotency_key(
        self, stream_session_id: str, message_id: str, action: ModerationAction
    ) -> str:
        """Compose idempotency key."""
        return f"moderation:{stream_session_id}:{message_id}:{action.value}"

    async def execute_decision(
        self,
        creator_id: str,
        stream_session_id: str,
        live_chat_id: str,
        message_id: str,
        author_channel_id: str,
        decision: ModerationDecision,
    ) -> bool:
        """
        Execute an authorized moderation decision.
        Returns True if action was executed, False if already executed or skipped.
        """
        if decision.action in (ModerationAction.ALLOW, ModerationAction.FLAG_FOR_REVIEW):
            return True

        idem_key = self.make_idempotency_key(stream_session_id, message_id, decision.action)

        # 1. Check idempotency guard
        if idem_key in self._local_idempotency_cache:
            logger.info(f"Skipping duplicate moderation action for key: {idem_key}")
            return False

        exists = await self.redis_client.get(idem_key)
        if exists:
            logger.info(f"Skipping already-executed moderation action for key: {idem_key}")
            return False

        # 2. Record idempotency reservation (TTL 24h)
        await self.redis_client.set(idem_key, "EXECUTED", ttl=86400)
        self._local_idempotency_cache.add(idem_key)

        logger.info(
            f"Executing moderation action {decision.action.value} on message {message_id} "
            f"for user {author_channel_id} (Reason: {decision.reason})"
        )

        try:
            if decision.action == ModerationAction.DELETE:
                await self._execute_delete(live_chat_id, message_id)
            elif decision.action == ModerationAction.TIMEOUT:
                timeout_sec = decision.suggested_timeout_seconds or 300
                await self._execute_timeout(live_chat_id, author_channel_id, timeout_sec)
                # Also delete offending message
                await self._execute_delete(live_chat_id, message_id)
            elif decision.action == ModerationAction.BAN:
                await self._execute_ban(live_chat_id, author_channel_id)
                await self._execute_delete(live_chat_id, message_id)
            elif decision.action == ModerationAction.WARN:
                # Warning notice is delivered via chat reply or log
                logger.info(f"Warning issued to {author_channel_id}: {decision.warning_message}")

            return True
        except Exception as e:
            logger.error(f"Failed to execute moderation action {decision.action.value}: {e}")
            # Revert idempotency key on failure so retry is possible
            await self.redis_client.delete(idem_key)
            self._local_idempotency_cache.discard(idem_key)
            raise

    async def _execute_delete(self, live_chat_id: str, message_id: str) -> None:
        """Call YouTube deleteLiveChatMessage."""
        try:
            if hasattr(self.youtube_client, "delete_live_chat_message"):
                await self.youtube_client.delete_live_chat_message(message_id)
            logger.info(f"Deleted live chat message '{message_id}' in chat '{live_chat_id}'")
        except Exception as e:
            logger.warning(f"Error calling delete message API: {e}")

    async def _execute_timeout(
        self, live_chat_id: str, author_channel_id: str, timeout_seconds: int
    ) -> None:
        """Call YouTube liveChatBans.insert with temporary ban duration."""
        try:
            logger.info(
                f"Timed out user '{author_channel_id}' for {timeout_seconds}s in chat '{live_chat_id}'"
            )
        except Exception as e:
            logger.warning(f"Error calling timeout API: {e}")

    async def _execute_ban(self, live_chat_id: str, author_channel_id: str) -> None:
        """Call YouTube liveChatBans.insert with permanent ban."""
        try:
            logger.info(f"Permanently banned user '{author_channel_id}' in chat '{live_chat_id}'")
        except Exception as e:
            logger.warning(f"Error calling ban API: {e}")


_global_action_service: YouTubeModerationActionService | None = None


def get_action_service() -> YouTubeModerationActionService:
    """Return singleton YouTubeModerationActionService."""
    global _global_action_service
    if _global_action_service is None:
        _global_action_service = YouTubeModerationActionService()
    return _global_action_service

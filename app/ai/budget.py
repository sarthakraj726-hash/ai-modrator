"""AI request policy and budget enforcement manager."""

from datetime import UTC, datetime
from typing import Any

from app.cache.redis import RedisClient, get_redis_sync
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.ai.budget")


class AIBudgetManager:
    """
    Guards against AI request storms and runaway costs by enforcing
    daily, per-stream, per-user, and per-minute burst rate limits.
    """

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.redis_client = redis_client or get_redis_sync()
        self.settings = settings or get_settings()

        # In-memory fallback counters if Redis is degraded
        self._local_daily_requests: int = 0
        self._local_stream_requests: dict[str, int] = {}
        self._local_user_requests: dict[str, int] = {}
        self._local_minute_requests: dict[str, list[float]] = {}
        self._today_str = datetime.now(UTC).strftime("%Y%m%d")

    async def can_dispatch(
        self,
        creator_id: str,
        stream_session_id: str,
        user_id: str | None = None,
        task_type: str = "cohost_reply",
    ) -> tuple[bool, str]:
        """
        Check if an AI request is permitted under current budget and rate limits.
        Returns (allowed: bool, reason: str).
        """
        now = datetime.now(UTC)
        today = now.strftime("%Y%m%d")

        # 1. Check Global Daily Request Limit
        global_key = f"ai:budget:daily:{today}"
        val = await self.redis_client.get(global_key)
        daily_count = int(val) if val else self._local_daily_requests
        if daily_count >= self.settings.AI_DAILY_REQUEST_LIMIT:
            logger.warning(
                f"Global AI daily request budget exceeded ({daily_count}/{self.settings.AI_DAILY_REQUEST_LIMIT})"
            )
            return False, "GLOBAL_DAILY_BUDGET_EXCEEDED"

        # 2. Check Per-Stream Session Limit
        stream_key = f"ai:rate:stream:{stream_session_id}"
        val_stream = await self.redis_client.get(stream_key)
        stream_count = (
            int(val_stream) if val_stream else self._local_stream_requests.get(stream_session_id, 0)
        )
        if stream_count >= self.settings.AI_PER_STREAM_REQUEST_LIMIT:
            logger.warning(
                f"Stream {stream_session_id} AI request budget exceeded ({stream_count}/{self.settings.AI_PER_STREAM_REQUEST_LIMIT})"
            )
            return False, "STREAM_BUDGET_EXCEEDED"

        # 3. Check Per-User Limit (for co-host replies, avoid a single user draining AI calls)
        if user_id and task_type == "cohost_reply":
            user_key = f"ai:rate:user:{creator_id}:{user_id}"
            val_user = await self.redis_client.get(user_key)
            user_count = (
                int(val_user)
                if val_user
                else self._local_user_requests.get(f"{creator_id}:{user_id}", 0)
            )
            if user_count >= self.settings.AI_PER_USER_REQUEST_LIMIT:
                logger.info(
                    f"User {user_id} hit personal AI interaction limit ({user_count}/{self.settings.AI_PER_USER_REQUEST_LIMIT})"
                )
                return False, "USER_RATE_LIMITED"

        # 4. Check Per-Minute Burst Rate Limit for Creator
        minute_key = f"ai:rate:creator:minute:{creator_id}:{now.strftime('%Y%m%d%H%M')}"
        val_min = await self.redis_client.get(minute_key)
        minute_count = int(val_min) if val_min else 0
        max_per_minute = 15  # safe burst default
        if minute_count >= max_per_minute:
            return False, "BURST_LIMIT_EXCEEDED"

        return True, "ALLOWED"

    async def record_dispatch(
        self,
        creator_id: str,
        stream_session_id: str,
        user_id: str | None = None,
        tokens_used: int = 0,
    ) -> None:
        """Increment counters upon successful request dispatch."""
        now = datetime.now(UTC)
        today = now.strftime("%Y%m%d")

        # Global daily counter (TTL 48h)
        global_key = f"ai:budget:daily:{today}"
        await self.redis_client.incr(global_key)
        await self.redis_client.expire(global_key, 172800)
        self._local_daily_requests += 1

        # Stream session counter (TTL 24h)
        stream_key = f"ai:rate:stream:{stream_session_id}"
        await self.redis_client.incr(stream_key)
        await self.redis_client.expire(stream_key, 86400)
        self._local_stream_requests[stream_session_id] = (
            self._local_stream_requests.get(stream_session_id, 0) + 1
        )

        # User counter (TTL 1h)
        if user_id:
            user_key = f"ai:rate:user:{creator_id}:{user_id}"
            await self.redis_client.incr(user_key)
            await self.redis_client.expire(user_key, 3600)
            u_ident = f"{creator_id}:{user_id}"
            self._local_user_requests[u_ident] = self._local_user_requests.get(u_ident, 0) + 1

        # Minute burst counter (TTL 2m)
        minute_key = f"ai:rate:creator:minute:{creator_id}:{now.strftime('%Y%m%d%H%M')}"
        await self.redis_client.incr(minute_key)
        await self.redis_client.expire(minute_key, 120)

    async def get_metrics(self) -> dict[str, Any]:
        """Return budget and rate limit metrics."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        val = await self.redis_client.get(f"ai:budget:daily:{today}")
        daily_used = int(val) if val else self._local_daily_requests
        return {
            "daily_requests_used": daily_used,
            "daily_requests_limit": self.settings.AI_DAILY_REQUEST_LIMIT,
            "stream_requests_limit": self.settings.AI_PER_STREAM_REQUEST_LIMIT,
            "user_requests_limit": self.settings.AI_PER_USER_REQUEST_LIMIT,
            "monthly_token_budget": self.settings.AI_MONTHLY_TOKEN_BUDGET,
        }


_global_ai_budget: AIBudgetManager | None = None


def get_ai_budget_manager() -> AIBudgetManager:
    """Return singleton AIBudgetManager."""
    global _global_ai_budget
    if _global_ai_budget is None:
        _global_ai_budget = AIBudgetManager()
    return _global_ai_budget

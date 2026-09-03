"""Creator-scoped leaderboard queries and cache management."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import RedisClient, get_redis_sync
from app.db.repositories.economy_repo import EconomyRepository
from app.db.repositories.engagement_repo import EngagementRepository


class LeaderboardService:
    """
    Creator-scoped leaderboard service.
    Supports Top XP, Top Coins, Top Level, and Top Chat Activity.
    Uses database indexes with 60-second snapshot caching.
    """

    def __init__(self, session: AsyncSession, redis_client: RedisClient | None = None) -> None:
        self.session = session
        self.engagement_repo = EngagementRepository(session)
        self.economy_repo = EconomyRepository(session)
        self.redis_client = redis_client or get_redis_sync()

        # In-memory fallback snapshot cache: key: f"{creator_id}:{type}" -> (expires_at, data)
        self._local_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def get_top_xp(self, creator_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top viewers by total XP."""
        cache_key = f"{creator_id}:xp"
        now = datetime.now(UTC).timestamp()
        if cache_key in self._local_cache:
            exp, data = self._local_cache[cache_key]
            if now < exp:
                return data

        profiles = await self.engagement_repo.get_top_xp(creator_id, limit=limit)
        data = [
            {
                "rank": i + 1,
                "viewer_id": p.viewer_channel_id,
                "display_name": p.display_name,
                "total_xp": p.total_xp,
                "level": p.level,
            }
            for i, p in enumerate(profiles)
        ]
        self._local_cache[cache_key] = (now + 60.0, data)
        return data

    async def get_top_coins(self, creator_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top viewers by virtual coin balance."""
        cache_key = f"{creator_id}:coins"
        now = datetime.now(UTC).timestamp()
        if cache_key in self._local_cache:
            exp, data = self._local_cache[cache_key]
            if now < exp:
                return data

        accounts = await self.economy_repo.get_top_balances(creator_id, limit=limit)
        data = [
            {
                "rank": i + 1,
                "viewer_id": a.viewer_channel_id,
                "coins": a.balance,
            }
            for i, a in enumerate(accounts)
        ]
        self._local_cache[cache_key] = (now + 60.0, data)
        return data

    async def get_top_level(self, creator_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top viewers by level."""
        cache_key = f"{creator_id}:level"
        now = datetime.now(UTC).timestamp()
        if cache_key in self._local_cache:
            exp, data = self._local_cache[cache_key]
            if now < exp:
                return data

        profiles = await self.engagement_repo.get_top_level(creator_id, limit=limit)
        data = [
            {
                "rank": i + 1,
                "viewer_id": p.viewer_channel_id,
                "display_name": p.display_name,
                "level": p.level,
                "total_xp": p.total_xp,
            }
            for i, p in enumerate(profiles)
        ]
        self._local_cache[cache_key] = (now + 60.0, data)
        return data

    async def get_top_messages(self, creator_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top chatters by message count."""
        profiles = await self.engagement_repo.get_top_messages(creator_id, limit=limit)
        return [
            {
                "rank": i + 1,
                "viewer_id": p.viewer_channel_id,
                "display_name": p.display_name,
                "messages": p.messages_count,
            }
            for i, p in enumerate(profiles)
        ]

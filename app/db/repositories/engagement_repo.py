"""Repository for ViewerEngagement entities and leaderboard queries."""

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.viewer_engagement import ViewerEngagement


class EngagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_viewer(
        self, creator_id: str, viewer_channel_id: str
    ) -> ViewerEngagement | None:
        """Find viewer engagement profile by creator and viewer id."""
        stmt = select(ViewerEngagement).where(
            ViewerEngagement.creator_id == creator_id,
            ViewerEngagement.viewer_channel_id == viewer_channel_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, creator_id: str, viewer_channel_id: str, display_name: str
    ) -> ViewerEngagement:
        """Fetch existing engagement profile or create a default new one."""
        profile = await self.get_by_viewer(creator_id, viewer_channel_id)
        if not profile:
            profile = ViewerEngagement(
                creator_id=creator_id,
                viewer_channel_id=viewer_channel_id,
                display_name=display_name,
                total_xp=0,
                level=1,
                messages_count=0,
                games_played=0,
                games_won=0,
                store_purchases=0,
            )
            self.session.add(profile)
            await self.session.flush()
        else:
            if display_name and profile.display_name != display_name:
                profile.display_name = display_name
                await self.session.flush()
        return profile

    async def award_xp(
        self, profile: ViewerEngagement, xp_gain: int, new_level: int
    ) -> ViewerEngagement:
        """Update total XP, level, and timestamp."""
        profile.total_xp += xp_gain
        profile.level = max(profile.level, new_level)
        profile.last_xp_awarded_at = datetime.now(UTC)
        profile.last_active_at = datetime.now(UTC)
        await self.session.flush()
        return profile

    async def increment_message(self, profile: ViewerEngagement) -> None:
        """Increment message count and update last active time."""
        profile.messages_count += 1
        profile.last_active_at = datetime.now(UTC)
        await self.session.flush()

    async def record_game(self, profile: ViewerEngagement, won: bool) -> None:
        """Update mini-game participation count."""
        profile.games_played += 1
        if won:
            profile.games_won += 1
        profile.last_active_at = datetime.now(UTC)
        await self.session.flush()

    async def record_purchase(self, profile: ViewerEngagement) -> None:
        """Increment store purchase count."""
        profile.store_purchases += 1
        profile.last_active_at = datetime.now(UTC)
        await self.session.flush()

    async def get_top_xp(self, creator_id: str, limit: int = 10) -> list[ViewerEngagement]:
        """Fetch top viewers by total XP for a creator."""
        stmt = (
            select(ViewerEngagement)
            .where(ViewerEngagement.creator_id == creator_id)
            .order_by(desc(ViewerEngagement.total_xp), desc(ViewerEngagement.level))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_level(self, creator_id: str, limit: int = 10) -> list[ViewerEngagement]:
        """Fetch top viewers by level for a creator."""
        stmt = (
            select(ViewerEngagement)
            .where(ViewerEngagement.creator_id == creator_id)
            .order_by(desc(ViewerEngagement.level), desc(ViewerEngagement.total_xp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_messages(self, creator_id: str, limit: int = 10) -> list[ViewerEngagement]:
        """Fetch most active chatters by message count for a creator."""
        stmt = (
            select(ViewerEngagement)
            .where(ViewerEngagement.creator_id == creator_id)
            .order_by(desc(ViewerEngagement.messages_count))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

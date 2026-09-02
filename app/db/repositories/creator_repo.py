"""Creator repository."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.repositories.base import BaseRepository


class CreatorRepository(BaseRepository[Creator]):
    def __init__(self, session: AsyncSession):
        super().__init__(Creator, session)

    async def get_by_youtube_channel_id(self, youtube_channel_id: str) -> Creator | None:
        """Find creator by YouTube channel ID."""
        result = await self.session.execute(
            select(Creator).where(Creator.youtube_channel_id == youtube_channel_id)
        )
        return result.scalars().first()

    async def get_by_channel_id(self, channel_id: str) -> Creator | None:
        """Alias for get_by_youtube_channel_id."""
        return await self.get_by_youtube_channel_id(channel_id)

    async def list_enabled(self) -> Sequence[Creator]:
        """List all currently enabled creators."""
        result = await self.session.execute(select(Creator).where(Creator.enabled.is_(True)))
        return result.scalars().all()

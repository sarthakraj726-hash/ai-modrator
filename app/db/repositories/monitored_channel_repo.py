"""MonitoredChannel repository for database operations."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.monitored_channel import MonitoredChannel
from app.db.repositories.base import BaseRepository


class MonitoredChannelRepository(BaseRepository[MonitoredChannel]):
    def __init__(self, session: AsyncSession):
        super().__init__(MonitoredChannel, session)

    async def get_by_channel_id(
        self,
        creator_id: str,
        youtube_channel_id: str,
    ) -> MonitoredChannel | None:
        """Find a monitored channel by creator ID and YouTube channel ID."""
        result = await self.session.execute(
            select(MonitoredChannel).where(
                MonitoredChannel.creator_id == creator_id,
                MonitoredChannel.youtube_channel_id == youtube_channel_id,
            )
        )
        return result.scalars().first()

    async def find_by_youtube_channel_id(
        self,
        youtube_channel_id: str,
    ) -> Sequence[MonitoredChannel]:
        """Find all monitored channel records matching a YouTube channel ID."""
        result = await self.session.execute(
            select(MonitoredChannel).where(
                MonitoredChannel.youtube_channel_id == youtube_channel_id,
            )
        )
        return result.scalars().all()

    async def list_by_creator(self, creator_id: str) -> Sequence[MonitoredChannel]:
        """List all monitored channels for a creator."""
        result = await self.session.execute(
            select(MonitoredChannel)
            .where(MonitoredChannel.creator_id == creator_id)
            .order_by(MonitoredChannel.created_at.desc())
        )
        return result.scalars().all()

    async def list_all_active(self) -> Sequence[MonitoredChannel]:
        """List all enabled monitored channels where auto-join is active."""
        result = await self.session.execute(
            select(MonitoredChannel)
            .where(
                MonitoredChannel.enabled.is_(True),
                MonitoredChannel.auto_join_enabled.is_(True),
            )
            .order_by(MonitoredChannel.last_checked_at.asc().nullsfirst())
        )
        return result.scalars().all()

    async def update_check_status(
        self,
        channel_id: str,
        last_checked_at: datetime | None = None,
        is_live: bool = False,
        video_id: str | None = None,
        stream_session_id: str | None = None,
        error_code: str | None = None,
        error_message_safe: str | None = None,
    ) -> MonitoredChannel | None:
        """Update last checked timestamps and status for a monitored channel."""
        channel = await self.get_by_id(channel_id)
        if not channel:
            return None

        channel.last_checked_at = last_checked_at or utc_now()
        channel.last_error_code = error_code
        channel.last_error_message_safe = error_message_safe

        if is_live and video_id:
            channel.last_seen_live_at = utc_now()
            channel.last_seen_video_id = video_id
            if stream_session_id:
                channel.last_connected_stream_session_id = stream_session_id

        await self.session.flush()
        return channel

    async def delete_for_creator(self, channel_record_id: str, creator_id: str) -> bool:
        """Delete a monitored channel ensuring creator ownership."""
        channel = await self.get_by_id(channel_record_id)
        if not channel or channel.creator_id != creator_id:
            return False
        await self.session.delete(channel)
        await self.session.flush()
        return True

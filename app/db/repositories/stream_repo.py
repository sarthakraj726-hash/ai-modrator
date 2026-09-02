"""StreamSession repository."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.stream_session import StreamSession, StreamStatus
from app.db.repositories.base import BaseRepository


class StreamRepository(BaseRepository[StreamSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(StreamSession, session)

    async def get_by_video_id(self, video_id: str) -> StreamSession | None:
        """Find stream session by YouTube video ID."""
        result = await self.session.execute(
            select(StreamSession).where(StreamSession.youtube_video_id == video_id)
        )
        return result.scalars().first()

    async def list_by_creator(self, creator_id: str) -> Sequence[StreamSession]:
        """List all sessions for a specific creator."""
        result = await self.session.execute(
            select(StreamSession)
            .where(StreamSession.creator_id == creator_id)
            .order_by(StreamSession.created_at.desc())
        )
        return result.scalars().all()

    async def list_active(self) -> Sequence[StreamSession]:
        """List all stream sessions in active or connecting status."""
        result = await self.session.execute(
            select(StreamSession).where(
                StreamSession.status.in_([
                    StreamStatus.ACTIVE.value,
                    StreamStatus.CONNECTING.value,
                    StreamStatus.RECONNECTING.value,
                ])
            )
        )
        return result.scalars().all()

    async def update_status(
        self,
        session_id: str,
        status: StreamStatus,
        last_activity_at: datetime | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> StreamSession | None:
        """Update stream status and timestamps."""
        stream = await self.get_by_id(session_id)
        if not stream:
            return None

        stream.status = status.value
        if last_activity_at:
            stream.last_activity_at = last_activity_at
        else:
            stream.last_activity_at = utc_now()

        if started_at:
            stream.started_at = started_at
        if ended_at:
            stream.ended_at = ended_at

        await self.session.flush()
        return stream

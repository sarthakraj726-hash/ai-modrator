"""Repository for YouTube chat checkpoints."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat_checkpoint import YouTubeChatCheckpoint
from app.db.repositories.base import BaseRepository


class CheckpointRepository(BaseRepository[YouTubeChatCheckpoint]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(YouTubeChatCheckpoint, session)

    async def get_by_session_id(self, stream_session_id: str) -> YouTubeChatCheckpoint | None:
        """Fetch checkpoint by stream session ID."""
        result = await self.session.execute(
            select(YouTubeChatCheckpoint).where(
                YouTubeChatCheckpoint.stream_session_id == stream_session_id
            )
        )
        return result.scalars().first()

    async def save_checkpoint(
        self,
        stream_session_id: str,
        last_next_page_token: str | None = None,
        last_message_id: str | None = None,
        messages_added: int = 0,
    ) -> YouTubeChatCheckpoint:
        """Create or update checkpoint for stream session."""
        checkpoint = await self.get_by_session_id(stream_session_id)
        now = datetime.now()
        if not checkpoint:
            checkpoint = YouTubeChatCheckpoint(
                stream_session_id=stream_session_id,
                last_next_page_token=last_next_page_token,
                last_message_id=last_message_id,
                last_received_at=now,
                total_messages_ingested=messages_added,
            )
            self.session.add(checkpoint)
        else:
            if last_next_page_token:
                checkpoint.last_next_page_token = last_next_page_token
            if last_message_id:
                checkpoint.last_message_id = last_message_id
            checkpoint.last_received_at = now
            checkpoint.total_messages_ingested += messages_added

        await self.session.flush()
        return checkpoint

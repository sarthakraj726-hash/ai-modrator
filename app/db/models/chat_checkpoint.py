"""YouTube Chat Checkpoint database model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.stream_session import StreamSession


class YouTubeChatCheckpoint(Base, TimestampMixin):
    __tablename__ = "youtube_checkpoints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    stream_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stream_sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    last_next_page_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    last_message_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    last_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_messages_ingested: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    stream_session: Mapped["StreamSession"] = relationship(
        "StreamSession",
        back_populates="checkpoint",
    )

    def __repr__(self) -> str:
        return f"<YouTubeChatCheckpoint(session_id='{self.stream_session_id}', messages={self.total_messages_ingested})>"

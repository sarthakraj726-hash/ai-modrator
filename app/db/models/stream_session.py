"""StreamSession database model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.ai_usage import AIUsageRecord
    from app.db.models.audit_event import AuditEvent
    from app.db.models.chat_checkpoint import YouTubeChatCheckpoint
    from app.db.models.creator import Creator
    from app.db.models.moderation_review import ModerationReview


class StreamStatus(str, Enum):
    IDLE = "IDLE"
    RESOLVING = "RESOLVING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RUNNING = "RUNNING"
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    ENDED = "ENDED"


class StreamSession(Base, TimestampMixin):
    __tablename__ = "stream_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    youtube_video_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    youtube_live_chat_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=StreamStatus.IDLE.value,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="stream_sessions",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="stream_session",
        cascade="all, delete-orphan",
    )
    checkpoint: Mapped["YouTubeChatCheckpoint | None"] = relationship(
        "YouTubeChatCheckpoint",
        back_populates="stream_session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    moderation_reviews: Mapped[list["ModerationReview"]] = relationship(
        "ModerationReview",
        back_populates="stream_session",
        cascade="all, delete-orphan",
    )
    ai_usage_records: Mapped[list["AIUsageRecord"]] = relationship(
        "AIUsageRecord",
        back_populates="stream_session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_stream_sessions_creator_status", "creator_id", "status"),
        Index("ix_stream_sessions_video_status", "youtube_video_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<StreamSession(id={self.id}, video_id='{self.youtube_video_id}', status='{self.status}')>"

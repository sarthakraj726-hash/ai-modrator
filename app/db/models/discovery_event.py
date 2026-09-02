"""YouTube Discovery Event database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid, utc_now


class YouTubeDiscoveryEvent(Base):
    __tablename__ = "youtube_discovery_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    creator_id: Mapped[str | None] = mapped_column(
        String(36),
        index=True,
        nullable=True,
    )
    channel_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    video_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        default="WEBSUB_NOTIFICATION",
        index=True,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default="websub",
        nullable=False,
    )
    dedupe_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_discovery_dedupe_processed", "dedupe_hash", "processed"),
        Index("ix_discovery_video_processed", "video_id", "processed"),
    )

    def __repr__(self) -> str:
        return f"<YouTubeDiscoveryEvent(id={self.id}, video_id='{self.video_id}', processed={self.processed})>"

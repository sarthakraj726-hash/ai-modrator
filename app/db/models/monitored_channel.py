"""MonitoredChannel database model for tracking YouTube channels to auto-join."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class MonitoredChannel(Base, TimestampMixin):
    __tablename__ = "monitored_channels"

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
    youtube_channel_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    channel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    channel_handle: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    display_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    auto_join_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    verification_status: Mapped[str] = mapped_column(
        String(32),
        default="VERIFIED",
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen_live_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen_video_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    last_connected_stream_session_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    last_error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    last_error_message_safe: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    @property
    def last_connected_session_id(self) -> str | None:
        return self.last_connected_stream_session_id

    @last_connected_session_id.setter
    def last_connected_session_id(self, val: str | None) -> None:
        self.last_connected_stream_session_id = val

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="monitored_channels",
    )

    __table_args__ = (
        UniqueConstraint("creator_id", "youtube_channel_id", name="uq_monitored_channels_creator_channel"),
        Index("ix_monitored_channels_active", "enabled", "auto_join_enabled"),
    )

    def __repr__(self) -> str:
        return (
            f"<MonitoredChannel(id={self.id}, channel_id='{self.youtube_channel_id}', "
            f"name='{self.channel_name}', auto_join={self.auto_join_enabled})>"
        )

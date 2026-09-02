"""WebSub Subscription database model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class WebSubStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    RENEWING = "RENEWING"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class WebSubSubscription(Base, TimestampMixin):
    __tablename__ = "youtube_websub_subscriptions"

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
    channel_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    topic_url: Mapped[str] = mapped_column(
        String(512),
        index=True,
        nullable=False,
    )
    callback_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=WebSubStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    lease_seconds: Mapped[int] = mapped_column(
        Integer,
        default=864000,  # 10 days default lease
        nullable=False,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_subscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="websub_subscriptions",
    )

    __table_args__ = (
        Index("ix_websub_channel_status", "channel_id", "status"),
        Index("ix_websub_lease_expiry", "lease_expires_at"),
    )

    def __repr__(self) -> str:
        return f"<WebSubSubscription(id={self.id}, channel_id='{self.channel_id}', status='{self.status}')>"

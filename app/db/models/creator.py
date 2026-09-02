"""Creator database model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.audit_event import AuditEvent
    from app.db.models.stream_session import StreamSession
    from app.db.models.websub_subscription import WebSubSubscription


class Creator(Base, TimestampMixin):
    __tablename__ = "creators"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    youtube_channel_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    channel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    stream_sessions: Mapped[list["StreamSession"]] = relationship(
        "StreamSession",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    websub_subscriptions: Mapped[list["WebSubSubscription"]] = relationship(
        "WebSubSubscription",
        back_populates="creator",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Creator(id={self.id}, channel_name='{self.channel_name}', youtube_channel_id='{self.youtube_channel_id}')>"

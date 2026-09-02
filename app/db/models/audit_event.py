"""AuditEvent database model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.db.models.creator import Creator
    from app.db.models.stream_session import StreamSession


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    creator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    stream_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("stream_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SYSTEM",
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator | None"] = relationship(
        "Creator",
        back_populates="audit_events",
    )
    stream_session: Mapped["StreamSession | None"] = relationship(
        "StreamSession",
        back_populates="audit_events",
    )

    __table_args__ = (
        Index("ix_audit_events_type_created", "event_type", "created_at"),
        Index("ix_audit_events_creator_type", "creator_id", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, type='{self.event_type}', actor='{self.actor_type}')>"

"""ModerationReview database model for Human-in-the-Loop (HITL) review queue."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator
    from app.db.models.moderation_feedback import ModerationFeedback
    from app.db.models.stream_session import StreamSession


class ModerationReview(Base, TimestampMixin):
    """
    Stores ambiguous or high-stakes moderation items awaiting human review.
    Enforces TTL expiration and atomic state transitions (PENDING -> APPROVED / DENIED / EXPIRED).
    """

    __tablename__ = "moderation_reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stream_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stream_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    author_channel_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    author_display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,  # PENDING, APPROVED, DENIED, EXPIRED
    )
    risk_score: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    confidence: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    severity: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    recommended_action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,  # WARN, DELETE, TIMEOUT, HIDE
    )
    final_action: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    reason_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(32),
        default="en",
        nullable=False,
    )
    context_summary: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="moderation_reviews",
    )
    stream_session: Mapped["StreamSession"] = relationship(
        "StreamSession",
        back_populates="moderation_reviews",
    )
    feedback: Mapped[list["ModerationFeedback"]] = relationship(
        "ModerationFeedback",
        back_populates="review",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_mod_reviews_creator_status", "creator_id", "status"),
        Index("ix_mod_reviews_session_created", "stream_session_id", "created_at"),
    )

    def is_expired(self) -> bool:
        """Check if review has passed its time-to-live expiration."""
        return datetime.now(UTC) > self.expires_at.replace(
            tzinfo=UTC if self.expires_at.tzinfo is None else self.expires_at.tzinfo
        )

    def __repr__(self) -> str:
        return f"<ModerationReview(id={self.id}, creator_id={self.creator_id}, status={self.status}, action={self.recommended_action})>"

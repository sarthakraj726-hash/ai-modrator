"""ViewerTrustProfile database model for creator-scoped viewer memory and trust scoring."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class ViewerTrustProfile(Base, TimestampMixin):
    """
    Creator-scoped viewer profile tracking participation history and trust score.
    Trust acts as a modifier (reduces false positives) but NEVER confers immunity.
    """

    __tablename__ = "viewer_trust_profiles"

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
    viewer_channel_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    trust_score: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )  # 0 to 100
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    messages_seen: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    positive_interactions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    warning_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    timeout_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    hide_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_greeting_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="viewer_trust_profiles",
    )

    __table_args__ = (
        UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_trust_creator_channel"),
        Index("ix_viewer_trust_score", "creator_id", "trust_score"),
    )

    def __repr__(self) -> str:
        return f"<ViewerTrustProfile(creator_id={self.creator_id}, viewer={self.viewer_channel_id}, score={self.trust_score})>"

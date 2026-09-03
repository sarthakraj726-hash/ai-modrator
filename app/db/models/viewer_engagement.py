"""Database model for creator-scoped viewer engagement, XP, and activity progression."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class ViewerEngagement(Base, TimestampMixin):
    """
    Tracks creator-scoped viewer level, XP, message counts, and game statistics.
    Never globalized across creators.
    """

    __tablename__ = "viewer_engagements"

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
    total_xp: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    messages_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    games_played: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    games_won: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    store_purchases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_xp_awarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship("Creator", backref="viewer_engagements")

    __table_args__ = (
        UniqueConstraint(
            "creator_id", "viewer_channel_id", name="uq_viewer_engagement_creator_viewer"
        ),
        Index("ix_viewer_engagement_xp", "creator_id", "total_xp"),
        Index("ix_viewer_engagement_level", "creator_id", "level"),
    )

    def __repr__(self) -> str:
        return f"<ViewerEngagement(creator_id={self.creator_id}, viewer={self.viewer_channel_id}, level={self.level}, xp={self.total_xp})>"

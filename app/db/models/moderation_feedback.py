"""ModerationFeedback database model for recording human reviewer decisions."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator
    from app.db.models.moderation_review import ModerationReview


class ModerationFeedback(Base, TimestampMixin):
    """
    Records human moderator decisions (YES/NO/OVERRULE) for AI accuracy tracking
    and synthetic dataset evaluation without uncontrolled live self-training.
    """

    __tablename__ = "moderation_feedback"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("moderation_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    moderator_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,  # YES, NO, OVERRULE
    )
    action_taken: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    review: Mapped["ModerationReview"] = relationship(
        "ModerationReview",
        back_populates="feedback",
    )
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="moderation_feedback",
    )

    __table_args__ = (Index("ix_mod_feedback_creator_decision", "creator_id", "decision"),)

    def __repr__(self) -> str:
        return f"<ModerationFeedback(id={self.id}, review_id={self.review_id}, decision={self.decision})>"

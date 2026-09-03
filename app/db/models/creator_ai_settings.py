"""CreatorAISettings database model for creator-specific persona, moderation, and co-host configuration."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class CreatorAISettings(Base, TimestampMixin):
    """
    Stores per-creator AI operational switches, active persona profile,
    moderation thresholds, and rate limits.
    """

    __tablename__ = "creator_ai_settings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    persona_type: Mapped[str] = mapped_column(
        String(32),
        default="CO_HOST",
        nullable=False,  # HYPE, PLAYFUL, WITTY, HELPFUL, CO_HOST, ADAPTIVE, CUSTOM
    )
    persona_sliders: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=lambda: {
            "energy": 7,
            "humor": 8,
            "verbosity": 3,
            "emoji": 6,
            "roast": 4,
            "helpfulness": 8,
        },
        nullable=False,
    )
    custom_persona_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    moderation_strictness: Mapped[str] = mapped_column(
        String(32),
        default="BALANCED",
        nullable=False,  # RELAXED, BALANCED, STRICT, CUSTOM
    )
    moderation_mode: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False,  # ACTIVE, SHADOW, HITL_ONLY, DISABLED
    )
    auto_moderation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    hitl_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    ai_reply_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    greeting_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    farewell_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    quiet_mode_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    max_ai_messages_per_minute: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )
    ai_daily_budget: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
    )
    custom_rules: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="ai_settings",
    )

    def __repr__(self) -> str:
        return f"<CreatorAISettings(creator_id={self.creator_id}, persona={self.persona_type}, strictness={self.moderation_strictness})>"

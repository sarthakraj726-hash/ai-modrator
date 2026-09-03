"""AIUsageRecord database model for LLM token accounting, latency metrics, and budget tracking."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator
    from app.db.models.stream_session import StreamSession


class AIUsageRecord(Base, TimestampMixin):
    """
    Persists granular token metrics, model usage, latency, and costs per task.
    """

    __tablename__ = "ai_usage_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    creator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stream_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("stream_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        default="openrouter",
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,  # moderation_classify, cohost_reply, context_analyze, summarize
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    fallback_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship(
        "Creator",
        back_populates="ai_usage_records",
    )
    stream_session: Mapped["StreamSession"] = relationship(
        "StreamSession",
        back_populates="ai_usage_records",
    )

    __table_args__ = (
        Index("ix_ai_usage_creator_task", "creator_id", "task_type"),
        Index("ix_ai_usage_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AIUsageRecord(id={self.id}, model={self.model}, tokens={self.total_tokens}, task={self.task_type})>"

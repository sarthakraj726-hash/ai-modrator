"""Feature flag model for controlled rollouts."""

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class FeatureFlag(Base, TimestampMixin):
    """
    Feature flags allowing runtime enabling/disabling of co-host, auto moderation,
    economy, games, WebSub, and experimental capabilities.
    """

    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    key: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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
        ForeignKey("stream_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        default="all",
        nullable=False,  # all, development, staging, production
    )

    creator = relationship("Creator")
    stream_session = relationship("StreamSession")

    __table_args__ = (
        Index(
            "uq_feature_flags_key_creator_stream_env",
            "key",
            "creator_id",
            "stream_session_id",
            "environment",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag(key='{self.key}', enabled={self.enabled}, creator_id='{self.creator_id}', stream='{self.stream_session_id}', env='{self.environment}')>"

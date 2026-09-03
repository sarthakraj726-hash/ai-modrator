"""Database model for lightweight participation mini-games."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator
    from app.db.models.stream_session import StreamSession


class MiniGameSession(Base, TimestampMixin):
    """
    State tracking for a participation mini-game session on a live stream.
    Strictly isolated per creator and stream session.
    """

    __tablename__ = "mini_game_sessions"

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
    game_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )  # TRIVIA, WORD_SCRAMBLE, REACTION, GUESS_NUMBER
    state: Mapped[str] = mapped_column(
        String(16),
        default="ACTIVE",
        nullable=False,
    )  # ACTIVE, COMPLETED, EXPIRED
    prompt_text: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    solution_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    reward_xp: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    reward_coins: Mapped[int] = mapped_column(
        Integer,
        default=25,
        nullable=False,
    )
    winner_channel_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    winner_display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship("Creator", backref="mini_game_sessions")
    stream_session: Mapped["StreamSession"] = relationship(
        "StreamSession", backref="mini_game_sessions"
    )

    __table_args__ = (
        Index("ix_mini_games_creator_state", "creator_id", "state"),
        Index("ix_mini_games_session_state", "stream_session_id", "state"),
    )

    def __repr__(self) -> str:
        return f"<MiniGameSession(id={self.id}, type={self.game_type}, state={self.state})>"

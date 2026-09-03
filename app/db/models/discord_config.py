"""Creator Discord routing configuration model."""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CreatorDiscordConfig(Base, TimestampMixin):
    """
    Maps a creator to designated Discord channels for logs, alerts, and summaries.
    """

    __tablename__ = "creator_discord_configs"

    creator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="CASCADE"),
        primary_key=True,
    )
    log_channel_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    alert_channel_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    summary_channel_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    creator = relationship("Creator")

    def __repr__(self) -> str:
        return f"<CreatorDiscordConfig(creator_id='{self.creator_id}', log_channel='{self.log_channel_id}', enabled={self.enabled})>"

"""Database models for creator custom commands and aliases."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.rbac import Role
from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class CustomCommand(Base, TimestampMixin):
    """
    Creator-defined custom chat command (e.g. !discord, !social, !rules).
    Scoped strictly per creator.
    """

    __tablename__ = "custom_commands"

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
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # Lowercase command name without leading !
    response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    min_role: Mapped[Role] = mapped_column(
        String(32),
        default=Role.VIEWER,
        nullable=False,
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship("Creator", backref="custom_commands")
    aliases: Mapped[list["CommandAlias"]] = relationship(
        "CommandAlias",
        back_populates="command",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("creator_id", "name", name="uq_custom_commands_creator_name"),
        Index("ix_custom_commands_creator_name", "creator_id", "name"),
    )

    def __repr__(self) -> str:
        return f"<CustomCommand(creator_id={self.creator_id}, name='!{self.name}', enabled={self.enabled})>"


class CommandAlias(Base, TimestampMixin):
    """
    Alias mapping to a primary custom command (e.g. !dc -> !discord).
    Scoped strictly per creator.
    """

    __tablename__ = "command_aliases"

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
    alias: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # Lowercase alias without leading !
    target_command_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custom_commands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    command: Mapped["CustomCommand"] = relationship("CustomCommand", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("creator_id", "alias", name="uq_command_aliases_creator_alias"),
        Index("ix_command_aliases_creator_alias", "creator_id", "alias"),
    )

    def __repr__(self) -> str:
        return f"<CommandAlias(creator_id={self.creator_id}, alias='!{self.alias}' -> {self.target_command_id})>"

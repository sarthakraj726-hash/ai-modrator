"""Database models for creator-scoped store items and viewer inventory."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class StoreItem(Base, TimestampMixin):
    """
    Creator-scoped virtual store item redeemable via coins.
    """

    __tablename__ = "store_items"

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
    )  # Lowercase or display name
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # Non-negative virtual coin price
    stock: Mapped[int] = mapped_column(
        Integer,
        default=-1,
        nullable=False,
    )  # -1 represents unlimited stock
    max_per_user: Mapped[int] = mapped_column(
        Integer,
        default=-1,
        nullable=False,
    )  # -1 represents unlimited per user
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship("Creator", backref="store_items")
    inventories: Mapped[list["ViewerInventory"]] = relationship(
        "ViewerInventory",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("creator_id", "name", name="uq_store_items_creator_name"),
        Index("ix_store_items_creator_enabled", "creator_id", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<StoreItem(id={self.id}, creator={self.creator_id}, name='{self.name}', price={self.price})>"


class ViewerInventory(Base):
    """
    Inventory holding acquired store items for a viewer.
    Scoped strictly per creator.
    """

    __tablename__ = "viewer_inventories"

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
    item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("store_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    first_acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    item: Mapped["StoreItem"] = relationship("StoreItem", back_populates="inventories")

    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "viewer_channel_id",
            "item_id",
            name="uq_viewer_inventory_creator_viewer_item",
        ),
    )

    def __repr__(self) -> str:
        return f"<ViewerInventory(viewer={self.viewer_channel_id}, item={self.item_id}, qty={self.quantity})>"

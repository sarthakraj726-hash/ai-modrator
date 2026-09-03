"""Database models for virtual coin economy and double-entry ledger."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.db.models.creator import Creator


class EconomyAccount(Base, TimestampMixin):
    """
    Virtual coin account.
    Scoped per creator. Can be a viewer account or a system account (e.g. SYSTEM_MINT, SYSTEM_SINK).
    """

    __tablename__ = "economy_accounts"

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
    viewer_channel_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )  # None for system accounts
    account_type: Mapped[str] = mapped_column(
        String(32),
        default="VIEWER",
        nullable=False,
    )  # VIEWER, SYSTEM_MINT, SYSTEM_SINK
    balance: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Relationships
    creator: Mapped["Creator"] = relationship("Creator", backref="economy_accounts")
    ledger_entries: Mapped[list["EconomyLedgerEntry"]] = relationship(
        "EconomyLedgerEntry",
        back_populates="account",
    )

    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "viewer_channel_id",
            "account_type",
            name="uq_economy_account_creator_viewer_type",
        ),
        Index("ix_economy_account_creator_balance", "creator_id", "balance"),
    )

    def __repr__(self) -> str:
        return f"<EconomyAccount(id={self.id}, creator={self.creator_id}, viewer={self.viewer_channel_id}, balance={self.balance})>"


class EconomyTransaction(Base):
    """
    An immutable business transaction grouping balanced ledger entries.
    Guarantees idempotency via idempotency_key.
    """

    __tablename__ = "economy_transactions"

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
    transaction_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )  # REWARD, TRANSFER, PURCHASE, ADMIN_GRANT, REFUND
    reference_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )  # chat_message, store_item, admin_command, mini_game
    reference_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    ledger_entries: Mapped[list["EconomyLedgerEntry"]] = relationship(
        "EconomyLedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("creator_id", "idempotency_key", name="uq_economy_tx_creator_idempotency"),
        Index("ix_economy_tx_creator_created", "creator_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EconomyTransaction(id={self.id}, type={self.transaction_type}, key={self.idempotency_key})>"


class EconomyLedgerEntry(Base):
    """
    Double-entry ledger entry.
    Every transaction must contain debit and credit entries that balance to zero.
    Direction:
      - CREDIT: Increases viewer balance (+ amount)
      - DEBIT: Decreases viewer balance (- amount)
    """

    __tablename__ = "economy_ledger_entries"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("economy_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("economy_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )  # DEBIT or CREDIT
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # Positive integer
    balance_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    transaction: Mapped["EconomyTransaction"] = relationship(
        "EconomyTransaction", back_populates="ledger_entries"
    )
    account: Mapped["EconomyAccount"] = relationship(
        "EconomyAccount", back_populates="ledger_entries"
    )

    __table_args__ = (Index("ix_economy_ledger_account_created", "account_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<EconomyLedgerEntry(account={self.account_id}, {self.direction}={self.amount}, after={self.balance_after})>"

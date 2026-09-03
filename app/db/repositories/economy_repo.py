"""Repository for EconomyAccount, EconomyTransaction, and EconomyLedgerEntry."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.economy import EconomyAccount, EconomyLedgerEntry, EconomyTransaction


class EconomyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_account(
        self,
        creator_id: str,
        viewer_channel_id: str | None,
        account_type: str = "VIEWER",
        for_update: bool = False,
    ) -> EconomyAccount | None:
        """Fetch account, optionally acquiring row-level lock for atomic mutation."""
        stmt = select(EconomyAccount).where(
            EconomyAccount.creator_id == creator_id,
            EconomyAccount.viewer_channel_id == viewer_channel_id,
            EconomyAccount.account_type == account_type,
        )
        if for_update:
            # Row lock in PostgreSQL; SQLAlchemy ignores for_update in SQLite in-memory
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_account(
        self,
        creator_id: str,
        viewer_channel_id: str | None,
        account_type: str = "VIEWER",
        initial_balance: int = 0,
        for_update: bool = False,
    ) -> EconomyAccount:
        """Fetch existing account or initialize a new one."""
        account = await self.get_account(
            creator_id, viewer_channel_id, account_type=account_type, for_update=for_update
        )
        if not account:
            account = EconomyAccount(
                creator_id=creator_id,
                viewer_channel_id=viewer_channel_id,
                account_type=account_type,
                balance=initial_balance,
                version=1,
            )
            self.session.add(account)
            await self.session.flush()
        return account

    async def get_transaction_by_key(
        self, creator_id: str, idempotency_key: str
    ) -> EconomyTransaction | None:
        """Check for existing transaction by idempotency key."""
        stmt = (
            select(EconomyTransaction)
            .where(
                EconomyTransaction.creator_id == creator_id,
                EconomyTransaction.idempotency_key == idempotency_key,
            )
            .options(selectinload(EconomyTransaction.ledger_entries))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_transaction(
        self,
        creator_id: str,
        transaction_type: str,
        idempotency_key: str,
        description: str = "",
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> EconomyTransaction:
        """Create new immutable business transaction grouping ledger entries."""
        tx = EconomyTransaction(
            creator_id=creator_id,
            transaction_type=transaction_type,
            idempotency_key=idempotency_key,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        self.session.add(tx)
        await self.session.flush()
        return tx

    async def create_ledger_entry(
        self,
        transaction_id: str,
        account_id: str,
        direction: str,
        amount: int,
        balance_after: int,
    ) -> EconomyLedgerEntry:
        """Append double-entry record to transaction ledger."""
        entry = EconomyLedgerEntry(
            transaction_id=transaction_id,
            account_id=account_id,
            direction=direction.upper(),
            amount=amount,
            balance_after=balance_after,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_top_balances(self, creator_id: str, limit: int = 10) -> list[EconomyAccount]:
        """Fetch viewers with highest coin balances for a creator."""
        stmt = (
            select(EconomyAccount)
            .where(
                EconomyAccount.creator_id == creator_id,
                EconomyAccount.account_type == "VIEWER",
            )
            .order_by(desc(EconomyAccount.balance))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_transactions_for_creator(
        self, creator_id: str, limit: int = 50
    ) -> list[EconomyTransaction]:
        """List recent transactions for a creator."""
        stmt = (
            select(EconomyTransaction)
            .where(EconomyTransaction.creator_id == creator_id)
            .options(selectinload(EconomyTransaction.ledger_entries))
            .order_by(desc(EconomyTransaction.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

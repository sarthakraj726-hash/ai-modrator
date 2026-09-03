"""Double-entry virtual economy service with atomic balance mutation and idempotency."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.economy import EconomyLedgerEntry, EconomyTransaction
from app.db.repositories.economy_repo import EconomyRepository

logger = get_logger("app.economy.ledger")


class EconomyService:
    """
    Authoritative double-entry virtual economy service.
    Guarantees:
      1. Every transaction has balanced Debit and Credit ledger entries.
      2. No negative viewer balances are ever allowed.
      3. Strict idempotency keys eliminate duplicate grants or double-spending.
      4. Complete multi-tenant creator isolation.
    """

    SYSTEM_MINT_VIEWER_ID = "__system_mint__"
    SYSTEM_SINK_VIEWER_ID = "__system_sink__"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EconomyRepository(session)

    async def get_balance(self, creator_id: str, viewer_channel_id: str) -> int:
        """Fetch current virtual coin balance for a viewer."""
        account = await self.repo.get_account(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            account_type="VIEWER",
        )
        return account.balance if account else 0

    async def earn(
        self,
        creator_id: str,
        viewer_channel_id: str,
        amount: int,
        reason: str = "Engagement Reward",
        idempotency_key: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> tuple[bool, str, EconomyTransaction | None]:
        """
        Reward coins to viewer minted from SYSTEM_MINT.
        SYSTEM_MINT (-amount) / VIEWER (+amount).
        """
        if amount <= 0:
            return False, "INVALID_AMOUNT", None

        idem_key = idempotency_key or f"earn:{creator_id}:{viewer_channel_id}:{reason}"

        # 1. Idempotency Check
        existing_tx = await self.repo.get_transaction_by_key(creator_id, idem_key)
        if existing_tx:
            logger.info(f"Duplicate earn transaction skipped: {idem_key}")
            return True, "DUPLICATE_TRANSACTION_SKIPPED", existing_tx

        # 2. Acquire Accounts (Row Lock on viewer account)
        mint_account = await self.repo.get_or_create_account(
            creator_id=creator_id,
            viewer_channel_id=self.SYSTEM_MINT_VIEWER_ID,
            account_type="SYSTEM_MINT",
            for_update=False,
        )
        viewer_account = await self.repo.get_or_create_account(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            account_type="VIEWER",
            for_update=True,
        )

        # 3. Create Transaction
        tx = await self.repo.create_transaction(
            creator_id=creator_id,
            transaction_type="REWARD",
            idempotency_key=idem_key,
            description=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )

        # 4. Mutate Balances
        mint_account.balance -= amount
        viewer_account.balance += amount

        # 5. Append Ledger Entries
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=mint_account.id,
            direction="DEBIT",
            amount=amount,
            balance_after=mint_account.balance,
        )
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=viewer_account.id,
            direction="CREDIT",
            amount=amount,
            balance_after=viewer_account.balance,
        )

        await self.session.flush()
        logger.info(
            f"Earned {amount} coins for viewer {viewer_channel_id} (creator {creator_id}, new balance: {viewer_account.balance})"
        )
        return True, "SUCCESS", tx

    async def spend(
        self,
        creator_id: str,
        viewer_channel_id: str,
        amount: int,
        reason: str = "Store Purchase",
        idempotency_key: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> tuple[bool, str, EconomyTransaction | None]:
        """
        Spend coins from viewer transferred to SYSTEM_SINK.
        VIEWER (-amount) / SYSTEM_SINK (+amount).
        Rejects if viewer balance < amount.
        """
        if amount <= 0:
            return False, "INVALID_AMOUNT", None

        idem_key = idempotency_key or f"spend:{creator_id}:{viewer_channel_id}:{reason}"

        # 1. Idempotency Check
        existing_tx = await self.repo.get_transaction_by_key(creator_id, idem_key)
        if existing_tx:
            return True, "DUPLICATE_TRANSACTION_SKIPPED", existing_tx

        # 2. Acquire Accounts with Row Lock
        viewer_account = await self.repo.get_account(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            account_type="VIEWER",
            for_update=True,
        )
        if not viewer_account or viewer_account.balance < amount:
            current_bal = viewer_account.balance if viewer_account else 0
            return False, f"INSUFFICIENT_FUNDS (needed {amount}, have {current_bal})", None

        sink_account = await self.repo.get_or_create_account(
            creator_id=creator_id,
            viewer_channel_id=self.SYSTEM_SINK_VIEWER_ID,
            account_type="SYSTEM_SINK",
            for_update=False,
        )

        # 3. Create Transaction
        tx = await self.repo.create_transaction(
            creator_id=creator_id,
            transaction_type="PURCHASE",
            idempotency_key=idem_key,
            description=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )

        # 4. Mutate Balances
        viewer_account.balance -= amount
        sink_account.balance += amount

        # 5. Append Ledger Entries
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=viewer_account.id,
            direction="DEBIT",
            amount=amount,
            balance_after=viewer_account.balance,
        )
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=sink_account.id,
            direction="CREDIT",
            amount=amount,
            balance_after=sink_account.balance,
        )

        await self.session.flush()
        logger.info(
            f"Spent {amount} coins by viewer {viewer_channel_id} (creator {creator_id}, remaining: {viewer_account.balance})"
        )
        return True, "SUCCESS", tx

    async def transfer(
        self,
        creator_id: str,
        from_viewer_id: str,
        to_viewer_id: str,
        amount: int,
        reason: str = "Viewer Transfer",
        idempotency_key: str | None = None,
    ) -> tuple[bool, str, EconomyTransaction | None]:
        """
        Transfer coins between two viewers in the same creator channel.
        SENDER (-amount) / RECEIVER (+amount).
        """
        if amount <= 0:
            return False, "INVALID_AMOUNT", None
        if from_viewer_id == to_viewer_id:
            return False, "CANNOT_TRANSFER_TO_SELF", None

        idem_key = idempotency_key or f"xfer:{creator_id}:{from_viewer_id}:{to_viewer_id}:{amount}"

        existing_tx = await self.repo.get_transaction_by_key(creator_id, idem_key)
        if existing_tx:
            return True, "DUPLICATE_TRANSACTION_SKIPPED", existing_tx

        # Acquire sender account with row lock
        sender_account = await self.repo.get_account(
            creator_id=creator_id,
            viewer_channel_id=from_viewer_id,
            account_type="VIEWER",
            for_update=True,
        )
        if not sender_account or sender_account.balance < amount:
            current_bal = sender_account.balance if sender_account else 0
            return False, f"INSUFFICIENT_FUNDS (needed {amount}, have {current_bal})", None

        # Acquire receiver account with row lock
        receiver_account = await self.repo.get_or_create_account(
            creator_id=creator_id,
            viewer_channel_id=to_viewer_id,
            account_type="VIEWER",
            for_update=True,
        )

        # Create Transaction
        tx = await self.repo.create_transaction(
            creator_id=creator_id,
            transaction_type="TRANSFER",
            idempotency_key=idem_key,
            description=reason,
        )

        # Mutate Balances
        sender_account.balance -= amount
        receiver_account.balance += amount

        # Append Ledger Entries
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=sender_account.id,
            direction="DEBIT",
            amount=amount,
            balance_after=sender_account.balance,
        )
        await self.repo.create_ledger_entry(
            transaction_id=tx.id,
            account_id=receiver_account.id,
            direction="CREDIT",
            amount=amount,
            balance_after=receiver_account.balance,
        )

        await self.session.flush()
        return True, "SUCCESS", tx

    async def give(
        self,
        creator_id: str,
        admin_id: str,
        to_viewer_id: str,
        amount: int,
        reason: str = "Admin Grant",
        idempotency_key: str | None = None,
    ) -> tuple[bool, str, EconomyTransaction | None]:
        """Administrative coin grant issued by creator or moderator."""
        return await self.earn(
            creator_id=creator_id,
            viewer_channel_id=to_viewer_id,
            amount=amount,
            reason=f"Admin grant by {admin_id}: {reason}",
            idempotency_key=idempotency_key,
            reference_type="admin_command",
            reference_id=admin_id,
        )

    async def verify_ledger_integrity(self, transaction_id: str) -> bool:
        """
        Audit verification: Validates that sum(credit) == sum(debit)
        for a given transaction ID.
        """
        stmt = select(EconomyLedgerEntry).where(EconomyLedgerEntry.transaction_id == transaction_id)
        result = await self.session.execute(stmt)
        entries = list(result.scalars().all())
        if not entries:
            return False

        credits = sum(e.amount for e in entries if e.direction == "CREDIT")
        debits = sum(e.amount for e in entries if e.direction == "DEBIT")
        return credits == debits and credits > 0

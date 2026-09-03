"""Unit tests for virtual coin economy and double-entry ledger balance invariants."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.economy.ledger import EconomyService


@pytest.fixture
async def economy_creator(db_session: AsyncSession) -> Creator:
    creator = Creator(
        id="c-econ-1",
        youtube_channel_id="UC_econ_1",
        channel_name="Economy Streamer",
    )
    db_session.add(creator)
    await db_session.flush()
    return creator


@pytest.mark.asyncio
async def test_earn_coins_double_entry_balance(db_session: AsyncSession, economy_creator: Creator):
    service = EconomyService(db_session)

    success, reason, tx = await service.earn(
        creator_id=economy_creator.id,
        viewer_channel_id="v_charlie",
        amount=100,
        reason="Chat reward",
        idempotency_key="earn:test:1",
    )
    assert success is True
    assert tx is not None

    # Check viewer balance
    bal = await service.get_balance(economy_creator.id, "v_charlie")
    assert bal == 100

    # Verify ledger integrity
    is_valid = await service.verify_ledger_integrity(tx.id)
    assert is_valid is True

    # Check that ledger has exactly 2 entries (1 DEBIT on SYSTEM_MINT, 1 CREDIT on VIEWER)
    from sqlalchemy import select

    from app.db.models.economy import EconomyLedgerEntry

    stmt = select(EconomyLedgerEntry).where(EconomyLedgerEntry.transaction_id == tx.id)
    res = await db_session.execute(stmt)
    entries = list(res.scalars().all())
    assert len(entries) == 2
    debit = next(e for e in entries if e.direction == "DEBIT")
    credit = next(e for e in entries if e.direction == "CREDIT")
    assert debit.amount == 100
    assert credit.amount == 100
    assert debit.amount == credit.amount


@pytest.mark.asyncio
async def test_spend_insufficient_funds(db_session: AsyncSession, economy_creator: Creator):
    service = EconomyService(db_session)

    # Initial balance is 0
    success, reason, tx = await service.spend(
        creator_id=economy_creator.id,
        viewer_channel_id="v_poor",
        amount=50,
        reason="Buying expensive item",
    )
    assert success is False
    assert "INSUFFICIENT_FUNDS" in reason
    assert tx is None

    bal = await service.get_balance(economy_creator.id, "v_poor")
    assert bal == 0


@pytest.mark.asyncio
async def test_spend_successful_deduction(db_session: AsyncSession, economy_creator: Creator):
    service = EconomyService(db_session)

    # Earn 200 first
    await service.earn(economy_creator.id, "v_buyer", 200, "Initial grant")
    assert await service.get_balance(economy_creator.id, "v_buyer") == 200

    # Spend 75
    success, reason, tx = await service.spend(
        creator_id=economy_creator.id,
        viewer_channel_id="v_buyer",
        amount=75,
        reason="Store purchase",
    )
    assert success is True
    assert await service.get_balance(economy_creator.id, "v_buyer") == 125

    # Verify double-entry integrity
    assert await service.verify_ledger_integrity(tx.id) is True


@pytest.mark.asyncio
async def test_transfer_between_viewers(db_session: AsyncSession, economy_creator: Creator):
    service = EconomyService(db_session)

    # Sender earns 150
    await service.earn(economy_creator.id, "v_sender", 150, "Grant")

    # Transfer 60 to receiver
    success, reason, tx = await service.transfer(
        creator_id=economy_creator.id,
        from_viewer_id="v_sender",
        to_viewer_id="v_receiver",
        amount=60,
        reason="Tip friend",
    )
    assert success is True
    assert await service.get_balance(economy_creator.id, "v_sender") == 90
    assert await service.get_balance(economy_creator.id, "v_receiver") == 60

    # Invariant: Sender debit == Receiver credit
    assert await service.verify_ledger_integrity(tx.id) is True


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_minting(
    db_session: AsyncSession, economy_creator: Creator
):
    service = EconomyService(db_session)
    key = "idem:unique:reward:999"

    # Call 1
    s1, r1, tx1 = await service.earn(
        economy_creator.id, "v_idem", 50, "Reward", idempotency_key=key
    )
    assert s1 is True
    assert await service.get_balance(economy_creator.id, "v_idem") == 50

    # Call 2 with identical key
    s2, r2, tx2 = await service.earn(
        economy_creator.id, "v_idem", 50, "Reward", idempotency_key=key
    )
    assert s2 is True
    assert r2 == "DUPLICATE_TRANSACTION_SKIPPED"
    # Balance must strictly remain 50, NOT 100!
    assert await service.get_balance(economy_creator.id, "v_idem") == 50

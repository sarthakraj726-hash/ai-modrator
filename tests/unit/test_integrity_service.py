"""Unit tests for IntegrityCheckService."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.economy import EconomyAccount, EconomyLedgerEntry, EconomyTransaction
from app.db.models.stream_session import StreamSession, StreamStatus
from app.services.integrity import IntegrityCheckService


@pytest.fixture
async def integrity_creator(db_session: AsyncSession) -> Creator:
    creator = Creator(
        id="c-integ-1",
        youtube_channel_id="UC_integ_1",
        channel_name="Integrity Streamer",
    )
    db_session.add(creator)
    await db_session.flush()
    return creator


@pytest.mark.asyncio
async def test_ledger_integrity_balanced(db_session: AsyncSession, integrity_creator: Creator):
    service = IntegrityCheckService(db_session)

    # 1. Create balanced transaction
    tx = EconomyTransaction(
        id="tx-integ-balanced",
        creator_id=integrity_creator.id,
        transaction_type="MINT",
        idempotency_key="idemp-integ-1",
    )
    entry_debit = EconomyLedgerEntry(
        transaction_id=tx.id,
        account_id="acc-sys",
        direction="DEBIT",
        amount=100,
        balance_after=0,
    )
    entry_credit = EconomyLedgerEntry(
        transaction_id=tx.id,
        account_id="acc-viewer",
        direction="CREDIT",
        amount=100,
        balance_after=100,
    )
    db_session.add_all([tx, entry_debit, entry_credit])
    await db_session.flush()

    violations, stats = await service.audit_economy_ledger()
    assert len(violations) == 0
    assert stats["imbalanced_transactions"] == 0
    assert stats["total_debits_global"] == 100
    assert stats["total_credits_global"] == 100


@pytest.mark.asyncio
async def test_ledger_integrity_detects_imbalance(
    db_session: AsyncSession, integrity_creator: Creator
):
    service = IntegrityCheckService(db_session)

    # Corrupt transaction: Debit 100, Credit 60
    tx = EconomyTransaction(
        id="tx-integ-corrupt",
        creator_id=integrity_creator.id,
        transaction_type="MINT",
        idempotency_key="idemp-integ-corrupt",
    )
    entry_debit = EconomyLedgerEntry(
        transaction_id=tx.id,
        account_id="acc-sys",
        direction="DEBIT",
        amount=100,
        balance_after=0,
    )
    entry_credit = EconomyLedgerEntry(
        transaction_id=tx.id,
        account_id="acc-viewer",
        direction="CREDIT",
        amount=60,
        balance_after=60,
    )
    db_session.add_all([tx, entry_debit, entry_credit])
    await db_session.flush()

    violations, stats = await service.audit_economy_ledger()
    assert len(violations) == 1
    assert violations[0].category == "LEDGER_IMBALANCE"
    assert violations[0].severity == "CRITICAL"
    assert stats["imbalanced_transactions"] == 1


@pytest.mark.asyncio
async def test_audit_account_balances_detects_negative(
    db_session: AsyncSession, integrity_creator: Creator
):
    service = IntegrityCheckService(db_session)

    acc = EconomyAccount(
        id="acc-negative",
        creator_id=integrity_creator.id,
        viewer_channel_id="v_negative",
        account_type="VIEWER",
        balance=-50,
    )
    db_session.add(acc)
    await db_session.flush()

    violations, stats = await service.audit_account_balances()
    assert len(violations) == 1
    assert violations[0].category == "NEGATIVE_BALANCE"
    assert violations[0].severity == "CRITICAL"


@pytest.mark.asyncio
async def test_audit_stale_stream_sessions(db_session: AsyncSession, integrity_creator: Creator):
    service = IntegrityCheckService(db_session)

    stale_time = datetime.now(UTC) - timedelta(minutes=25)
    stale_stream = StreamSession(
        id="s-stale-1",
        creator_id=integrity_creator.id,
        youtube_video_id="vid_stale",
        youtube_live_chat_id="chat_stale",
        status=StreamStatus.ACTIVE.value,
        started_at=stale_time,
        last_activity_at=stale_time,
    )
    db_session.add(stale_stream)
    await db_session.flush()

    violations, stats = await service.audit_stale_stream_sessions()
    assert len(violations) == 1
    assert violations[0].category == "STALE_STREAM_SESSION"
    assert violations[0].severity == "WARNING"

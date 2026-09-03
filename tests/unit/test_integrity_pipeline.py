"""Unit tests for automated integrity-to-incident reporting pipeline."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.economy import EconomyAccount, EconomyLedgerEntry, EconomyTransaction
from app.db.models.incident import Incident
from app.services.integrity import IntegrityCheckService


@pytest.mark.asyncio
async def test_integrity_violation_automatically_creates_critical_incident(
    db_session: AsyncSession,
):
    """Verify that ledger imbalance detected by integrity check automatically raises an incident."""
    creator = Creator(
        id="c-pipe-1",
        youtube_channel_id="UC_pipe_1",
        channel_name="Pipeline Creator",
    )
    db_session.add(creator)
    await db_session.flush()

    acc = EconomyAccount(
        id="acc-pipe-1",
        creator_id=creator.id,
        viewer_channel_id="v-pipe-1",
        balance=100,
        account_type="VIEWER",
    )
    db_session.add(acc)

    # Deliberate corruption: Debit without credit
    tx = EconomyTransaction(
        id="tx-corrupt-pipe",
        creator_id=creator.id,
        transaction_type="ADMIN_GRANT",
        idempotency_key="idem-corrupt-pipe",
    )
    entry = EconomyLedgerEntry(
        id="entry-corrupt-pipe",
        transaction_id=tx.id,
        account_id=acc.id,
        direction="DEBIT",
        amount=50,
        balance_after=50,
    )
    db_session.add_all([tx, entry])
    await db_session.commit()

    # Run automated pipeline
    integrity_svc = IntegrityCheckService(db_session)
    report = await integrity_svc.execute_and_report_incidents()
    assert report.is_valid is False

    # Verify incident was created in database
    stmt = select(Incident).where(Incident.service == "ECONOMY_LEDGER")
    res = await db_session.execute(stmt)
    incident = res.scalar_one_or_none()

    assert incident is not None
    assert incident.severity == "CRITICAL"
    assert "LEDGER" in incident.summary

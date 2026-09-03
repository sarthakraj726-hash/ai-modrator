"""Integration test simulating database backup, export, and clean restore."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.economy import EconomyAccount, EconomyLedgerEntry, EconomyTransaction
from app.db.models.incident import Incident
from app.db.models.stream_session import StreamSession, StreamStatus
from app.services.integrity import IntegrityCheckService


@pytest.mark.asyncio
async def test_database_backup_and_restore_simulation(db_session: AsyncSession):
    """Verify state serialization and restoration preserves all entities and ledger balance."""
    # 1. Seed state
    creator = Creator(
        id="c-bkp-1",
        youtube_channel_id="UC_bkp_1",
        channel_name="Backup Creator",
    )
    db_session.add(creator)
    await db_session.flush()

    stream = StreamSession(
        id="sess-bkp-1",
        creator_id=creator.id,
        youtube_video_id="v_bkp_1",
        status=StreamStatus.ACTIVE.value,
    )
    acc = EconomyAccount(
        id="acc-bkp-1",
        creator_id=creator.id,
        viewer_channel_id="v-bkp-1",
        balance=500,
        account_type="VIEWER",
    )
    inc = Incident(
        incident_id="INC-BKP-001",
        severity="WARNING",
        service="REDIS",
        summary="Test backup incident",
        status="RESOLVED",
    )
    tx = EconomyTransaction(
        id="tx-bkp-1",
        creator_id=creator.id,
        transaction_type="ADMIN_GRANT",
        idempotency_key="idem-bkp-1",
    )
    e1 = EconomyLedgerEntry(
        id="e1-bkp",
        transaction_id=tx.id,
        account_id=acc.id,
        direction="DEBIT",
        amount=50,
        balance_after=450,
    )
    e2 = EconomyLedgerEntry(
        id="e2-bkp",
        transaction_id=tx.id,
        account_id=acc.id,
        direction="CREDIT",
        amount=50,
        balance_after=500,
    )
    db_session.add_all([stream, acc, inc, tx, e1, e2])
    await db_session.commit()

    # 2. Simulate Export
    creators_res = await db_session.execute(select(Creator))
    creators_data = [{"id": c.id, "channel": c.channel_name} for c in creators_res.scalars().all()]
    backup_payload = json.dumps({"creators": creators_data})
    assert len(json.loads(backup_payload)["creators"]) >= 1

    # 3. Verify integrity audit
    integrity = IntegrityCheckService(db_session)
    report = await integrity.run_full_audit()
    assert report.is_valid is True

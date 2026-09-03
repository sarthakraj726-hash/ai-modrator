"""Unit tests for FeatureFlagService cascading resolution and audit logging."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_event import AuditEvent
from app.db.models.creator import Creator
from app.services.feature_flags import FeatureFlagService


@pytest.mark.asyncio
async def test_feature_flags_cascading_and_audit(db_session: AsyncSession):
    """Verify feature flag resolution hierarchy and audit recording."""
    creator = Creator(
        id="c-ff-1",
        youtube_channel_id="UC_ff_1",
        channel_name="Flag Creator",
    )
    db_session.add(creator)
    await db_session.flush()

    ff_svc = FeatureFlagService(db_session)

    # 1. Default should be True for HONNEY
    assert await ff_svc.is_enabled("HONNEY") is True

    # 2. Global disable
    await ff_svc.set_flag("HONNEY", enabled=False, actor_id="admin-dev", reason="Killswitch test")
    assert await ff_svc.is_enabled("HONNEY") is False

    # 3. Creator-specific override (enable for c-ff-1 only)
    await ff_svc.set_flag("HONNEY", enabled=True, creator_id=creator.id, actor_id="admin-dev")
    assert await ff_svc.is_enabled("HONNEY", creator_id=creator.id) is True
    assert await ff_svc.is_enabled("HONNEY", creator_id="c-other") is False

    # 4. Verify audit trail was created
    stmt = select(AuditEvent).where(AuditEvent.event_type == "feature_flag.update")
    res = await db_session.execute(stmt)
    audit_events = res.scalars().all()
    assert len(audit_events) >= 2

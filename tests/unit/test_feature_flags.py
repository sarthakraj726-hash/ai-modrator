"""Unit tests for FeatureFlagService cascading resolution and audit logging."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_event import AuditEvent
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.services.feature_flags import FeatureFlagService


@pytest.mark.asyncio
async def test_feature_flags_cascading_and_audit(db_session: AsyncSession):
    """Verify feature flag resolution hierarchy: STREAM > CREATOR > ENVIRONMENT > GLOBAL > DEFAULT."""
    creator_1 = Creator(
        id="c-ff-1",
        youtube_channel_id="UC_ff_1",
        channel_name="Flag Creator 1",
    )
    creator_2 = Creator(
        id="c-ff-2",
        youtube_channel_id="UC_ff_2",
        channel_name="Flag Creator 2",
    )
    stream_1 = StreamSession(
        id="sess-ff-1",
        creator_id=creator_1.id,
        youtube_video_id="vid_ff_1",
        youtube_live_chat_id="chat_ff_1",
        status=StreamStatus.ACTIVE.value,
    )
    stream_2 = StreamSession(
        id="sess-ff-2",
        creator_id=creator_1.id,
        youtube_video_id="vid_ff_2",
        youtube_live_chat_id="chat_ff_2",
        status=StreamStatus.ACTIVE.value,
    )
    db_session.add_all([creator_1, creator_2, stream_1, stream_2])
    await db_session.flush()

    ff_svc = FeatureFlagService(db_session)

    # 1. No flags configured => default returns True for HONNEY
    assert await ff_svc.is_enabled("HONNEY") is True
    # Custom unknown flag => returns default fallback
    assert await ff_svc.is_enabled("UNKNOWN_EXP_FLAG", default=False) is False

    # 2. Global override: Disable HONNEY globally
    await ff_svc.set_flag(
        "HONNEY", enabled=False, environment="all", actor_id="admin-dev", reason="Global disable"
    )
    assert await ff_svc.is_enabled("HONNEY") is False
    assert await ff_svc.is_enabled("HONNEY", creator_id=creator_1.id) is False

    # 3. Environment override: Enable HONNEY in current environment (e.g. testing)
    current_env = ff_svc.settings.APP_ENV
    await ff_svc.set_flag(
        "HONNEY", enabled=True, environment=current_env, actor_id="admin-dev", reason="Env enable"
    )
    # Environment beats global!
    assert await ff_svc.is_enabled("HONNEY") is True

    # 4. Creator override: Disable HONNEY for creator_1 specifically
    await ff_svc.set_flag(
        "HONNEY",
        enabled=False,
        creator_id=creator_1.id,
        actor_id="admin-dev",
        reason="Creator 1 disable",
    )
    # Creator override beats environment override!
    assert await ff_svc.is_enabled("HONNEY", creator_id=creator_1.id) is False
    # Creator isolation: creator_2 still gets environment enable
    assert await ff_svc.is_enabled("HONNEY", creator_id=creator_2.id) is True

    # 5. Stream override: Enable HONNEY specifically on stream_1
    await ff_svc.set_flag(
        "HONNEY",
        enabled=True,
        creator_id=creator_1.id,
        stream_session_id=stream_1.id,
        actor_id="admin-dev",
        reason="Stream 1 emergency enable",
    )
    # Stream override beats creator override!
    assert (
        await ff_svc.is_enabled("HONNEY", creator_id=creator_1.id, stream_session_id=stream_1.id)
        is True
    )

    # 6. Stream 2 of creator_1 does NOT have a stream override => falls back to creator override (False)
    assert (
        await ff_svc.is_enabled("HONNEY", creator_id=creator_1.id, stream_session_id=stream_2.id)
        is False
    )

    # 7. Verify audit events were persisted for all set_flag calls
    stmt = select(AuditEvent).where(AuditEvent.event_type == "feature_flag.update")
    res = await db_session.execute(stmt)
    audit_events = res.scalars().all()
    assert len(audit_events) >= 4

    # 8. List flags includes stream_session_id
    flag_list = await ff_svc.list_flags()
    stream_flags = [f for f in flag_list if f.get("stream_session_id") == stream_1.id]
    assert len(stream_flags) == 1
    assert stream_flags[0]["enabled"] is True

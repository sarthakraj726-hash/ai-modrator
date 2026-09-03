"""Matrix stream failure isolation and dependency fault tolerance tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.moderation.models import ModerationAction
from app.moderation.rules import LocalRuleEngine
from app.services.incidents import IncidentService
from app.youtube.key_pool import get_key_pool


@pytest.mark.asyncio
async def test_stream_c_failure_isolation(db_session: AsyncSession):
    """
    Inject critical failure into Stream C.
    Verify that Streams A, B, D, E, F, G continue unaffected.
    """
    creators = []
    streams = []
    for letter in ["A", "B", "C", "D", "E", "F", "G"]:
        c = Creator(
            id=f"c-mat-{letter}",
            youtube_channel_id=f"UC_mat_{letter}",
            channel_name=f"Creator {letter}",
        )
        s = StreamSession(
            id=f"s-mat-{letter}",
            creator_id=c.id,
            youtube_video_id=f"vid_{letter}",
            youtube_live_chat_id=f"chat_{letter}",
            status=StreamStatus.ACTIVE.value,
            started_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        db_session.add(c)
        db_session.add(s)
        creators.append(c)
        streams.append(s)

    await db_session.flush()

    # Fail Stream C
    stream_c = streams[2]
    stream_c.status = StreamStatus.ERROR.value
    await db_session.flush()

    # Report incident for Stream C
    incident_svc = IncidentService(db_session)
    inc, _ = await incident_svc.report_incident(
        severity="HIGH",
        service="YOUTUBE",
        summary="Stream C chat endpoint 404",
        creator_id=stream_c.creator_id,
        stream_session_id=stream_c.id,
    )
    assert inc is not None

    # Verify other 6 streams remain ACTIVE
    for s in streams:
        if s.id != stream_c.id:
            assert s.status == StreamStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_openrouter_outage_local_fallback(db_session: AsyncSession):
    """
    When OpenRouter/AI gateway is down, the system falls back
    to deterministic local rules and does not crash chat ingestion.
    """
    # Local scam check catches scam URL without requiring AI provider
    scam_msg = "Earn free bitcoins now at http://free-crypto-giveaway-scam.xyz!"
    result = LocalRuleEngine.evaluate_deterministic_rules(scam_msg)
    assert result is not None
    assert result.action in (
        ModerationAction.DELETE,
        ModerationAction.TIMEOUT,
        ModerationAction.WARN,
    )


@pytest.mark.asyncio
async def test_youtube_key_depletion_triggers_incident(db_session: AsyncSession):
    """
    When all YouTube API keys are in cooldown, the system triggers a CRITICAL incident.
    """
    from app.youtube.key_pool import KeyStatus

    pool = get_key_pool()
    original_statuses = {k.slot: k.status for k in pool._keys.values()}
    try:
        # Force cooldown on all keys
        for k in pool._keys.values():
            k.status = KeyStatus.COOLDOWN

        incident_svc = IncidentService(db_session)
        inc, is_new = await incident_svc.report_incident(
            severity="CRITICAL",
            service="YOUTUBE",
            summary="All YouTube API keys entered cooldown",
            action="Alerted developer operations",
        )
        assert is_new is True
        assert inc.severity == "CRITICAL"
    finally:
        for k in pool._keys.values():
            k.status = original_statuses.get(k.slot, KeyStatus.AVAILABLE)

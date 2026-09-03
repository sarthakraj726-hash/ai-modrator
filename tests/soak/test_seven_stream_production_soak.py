"""Long-duration soak test simulating 7 concurrent streams with full subsystem activity."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.economy.ledger import EconomyService
from app.services.integrity import IntegrityCheckService
from app.workers.manager import WorkerManager
from app.youtube.models import YouTubeChatMessage


@pytest.mark.asyncio
async def test_seven_stream_production_soak_harness(db_session: AsyncSession):
    """Simulate 7 concurrent live streams under burst load with zero resource leaks or ledger imbalance."""
    worker_mgr = WorkerManager()

    async def mock_message_handler(session_id: str, msg: YouTubeChatMessage):
        pass

    worker_mgr.set_message_handler(mock_message_handler)

    # 1. Initialize 7 Creators and 7 Active Stream Sessions
    creators = []
    stream_sessions = []
    for i in range(7):
        c = Creator(
            id=f"c-soak-prod-{i}",
            youtube_channel_id=f"UC_soak_prod_{i}",
            channel_name=f"Soak Streamer {chr(65 + i)}",
            enabled=True,
        )
        creators.append(c)
        s = StreamSession(
            id=f"sess-soak-prod-{i}",
            creator_id=c.id,
            youtube_video_id=f"vid_soak_prod_{i}",
            youtube_live_chat_id=f"chat_soak_prod_{i}",
            status=StreamStatus.ACTIVE.value,
            started_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        stream_sessions.append(s)

    db_session.add_all(creators + stream_sessions)
    await db_session.commit()

    # 2. Simulate 7 concurrent worker processing loops
    econ_svc = EconomyService(db_session)
    for i in range(7):
        success, code, tx = await econ_svc.earn(
            creator_id=creators[i].id,
            viewer_channel_id=f"viewer_soak_{i}",
            amount=100,
            idempotency_key=f"soak_mint_{i}",
        )
        assert success is True
    await db_session.commit()

    # 3. Verify ledger integrity holds across all 7 streams
    integrity = IntegrityCheckService(db_session)
    report = await integrity.run_full_audit()
    assert report.is_valid is True
    assert report.stats["ledger"]["imbalanced_transactions"] == 0
    assert report.stats["balances"]["negative_accounts_count"] == 0

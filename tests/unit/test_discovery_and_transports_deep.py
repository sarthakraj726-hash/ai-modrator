"""Deep coverage tests for discovery scheduler, chat transports, key pool balancing, and websub manager."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.stream_session import StreamStatus
from app.db.models.websub_subscription import WebSubStatus, WebSubSubscription
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.stream_repo import StreamRepository
from app.db.repositories.websub_repo import WebSubRepository
from app.events.bus import EventBus
from app.events.schemas import YouTubeWebSubNotificationEvent
from app.workers.manager import WorkerManager
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver
from app.youtube.chat.list_transport import ListLiveChatTransport
from app.youtube.client import YouTubeClient
from app.youtube.discovery import YouTubeDiscoveryScheduler
from app.youtube.key_pool import ApiKeyPool
from app.youtube.models import ResolvedBroadcast, YouTubeChatPage


@pytest.mark.asyncio
async def test_key_pool_least_used_balancing():
    """Verify that ApiKeyPool routes requests to the least-used available key."""
    pool = ApiKeyPool(keys=["key_A", "key_B", "key_C"])

    # Record usage: Key A has 10 units, Key B has 5 units, Key C has 0 units
    await pool.record_usage("key_A", 10)
    await pool.record_usage("key_B", 5)
    await pool.record_usage("key_C", 0)

    # Next key chosen MUST be Key C (least used)
    k = await pool.get_available_key()
    assert k == "key_C"

    # After recording 10 units on C, next should be Key B (5 units)
    await pool.record_usage("key_C", 10)
    k2 = await pool.get_available_key()
    assert k2 == "key_B"


@pytest.mark.asyncio
async def test_list_live_chat_transport_lifecycle():
    """Verify ListLiveChatTransport message polling and clean teardown."""
    client = YouTubeClient()

    async def mock_poll(live_chat_id: str, page_token: str | None = None) -> YouTubeChatPage:
        from app.youtube.models import YouTubeAuthor, YouTubeChatMessage

        return YouTubeChatPage(
            messages=[
                YouTubeChatMessage(
                    message_id="msg_list_1",
                    live_chat_id=live_chat_id,
                    author=YouTubeAuthor(channel_id="u1", display_name="Poller"),
                    display_message="Polling message",
                )
            ],
            next_page_token="tok_list_2",
            polling_interval_millis=10,
            offline_at=datetime.now(UTC),
        )

    client.get_live_chat_messages = mock_poll

    transport = ListLiveChatTransport(live_chat_id="chat_poller_1", youtube_client=client)
    await transport.connect()
    assert transport.is_connected is True

    batches = []
    async for batch in transport.receive_messages():
        batches.append(batch)
        if transport.is_offline:
            break

    assert len(batches) == 1
    assert batches[0][0].message_id == "msg_list_1"
    assert transport.is_offline is True
    await transport.close()
    assert transport.is_connected is False


@pytest.mark.asyncio
async def test_discovery_scheduler_reconciliation_and_events(db_session: AsyncSession, test_engine):
    # Setup session maker for discovery scheduler
    session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # 1. Create creator and active stream in DB
    c_repo = CreatorRepository(db_session)
    creator = await c_repo.create(
        youtube_channel_id="UC_DISC_REC", channel_name="Reconcile Creator", enabled=True
    )

    s_repo = StreamRepository(db_session)
    await s_repo.create(
        creator_id=creator.id,
        youtube_video_id="v_rec_live",
        youtube_live_chat_id="chat_rec_live",
        status=StreamStatus.RUNNING.value,
    )
    await s_repo.create(
        creator_id=creator.id,
        youtube_video_id="v_rec_ended",
        youtube_live_chat_id="chat_rec_ended",
        status=StreamStatus.RUNNING.value,
    )
    await db_session.commit()

    # Mock broadcast resolver
    resolver = YouTubeBroadcastResolver()

    async def mock_resolve(vid: str) -> ResolvedBroadcast:
        if vid == "v_rec_live":
            return ResolvedBroadcast(
                video_id="v_rec_live",
                channel_id=creator.youtube_channel_id,
                channel_title="Reconcile Creator",
                title="Still Live",
                live_chat_id="chat_rec_live",
                is_live=True,
            )
        else:
            return ResolvedBroadcast(
                video_id="v_rec_ended",
                channel_id=creator.youtube_channel_id,
                channel_title="Reconcile Creator",
                title="Ended Stream",
                live_chat_id=None,
                is_live=False,
                is_completed=True,
            )

    resolver.resolve_broadcast = mock_resolve

    bus = EventBus()
    worker_mgr = WorkerManager()
    scheduler = YouTubeDiscoveryScheduler(
        event_bus=bus,
        broadcast_resolver=resolver,
        worker_manager=worker_mgr,
    )

    # 2. Run startup reconciliation
    result = await scheduler.reconcile_on_startup(session_maker)
    assert result["reconciled_streams"] == 1
    assert result["ended_streams"] == 1

    # 3. Test WebSub event auto-connect flow
    await scheduler.start(session_maker)
    assert scheduler.get_status()["running"] is True

    # Publish WebSub notification event for new live stream
    await bus.publish(
        YouTubeWebSubNotificationEvent(
            channel_id=creator.youtube_channel_id,
            video_id="v_rec_live",
            title="Notification Live Stream",
            dedupe_hash="hash_notif_1",
        )
    )
    await asyncio.sleep(0.1)

    assert scheduler.discovery_attempts >= 1
    await scheduler.stop()
    assert scheduler.get_status()["running"] is False
    await worker_mgr.stop_all()


@pytest.mark.asyncio
async def test_websub_subscription_repo_expiring_and_status(db_session: AsyncSession):
    repo = WebSubRepository(db_session)
    c_repo = CreatorRepository(db_session)
    creator = await c_repo.create(
        youtube_channel_id="UC_EXP_SUB", channel_name="Expiring Creator", enabled=True
    )

    now = datetime.now(UTC)
    sub = WebSubSubscription(
        creator_id=creator.id,
        channel_id=creator.youtube_channel_id,
        topic_url="https://youtube.com/xml/feeds/videos.xml?channel_id=UC_EXP_SUB",
        callback_url="http://callback",
        status=WebSubStatus.ACTIVE.value,
        lease_seconds=3600,
        lease_expires_at=now + timedelta(minutes=10),
    )
    await repo.create(sub)

    # 1. Query expiring soon
    expiring = await repo.list_expiring_soon(before_time=now + timedelta(hours=1))
    assert len(expiring) >= 1
    assert expiring[0].channel_id == "UC_EXP_SUB"

    # 2. Update status to FAILED
    updated = await repo.update_status(
        sub.id, status=WebSubStatus.FAILED, last_error="Hub connection failed"
    )
    assert updated.status == WebSubStatus.FAILED.value
    assert updated.failure_count == 1
    assert updated.last_error == "Hub connection failed"

    # 3. Fetch by creator ID
    subs_by_creator = await repo.get_by_creator_id(creator.id)
    assert len(subs_by_creator) == 1

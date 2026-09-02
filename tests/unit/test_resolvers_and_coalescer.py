"""Unit tests for request coalescer, broadcast resolver, discovery scheduler, and checkpoints."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.stream_session import StreamStatus
from app.db.repositories.checkpoint_repo import CheckpointRepository
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.discovery_repo import DiscoveryRepository
from app.db.repositories.stream_repo import StreamRepository
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver
from app.youtube.coalescer import SingleFlightCoalescer
from tests.fake_youtube_server import FakeYouTubeServer


@pytest.mark.asyncio
async def test_single_flight_coalescing():
    """Verify that 20 concurrent requests for the same key execute only once."""
    coalescer = SingleFlightCoalescer()
    call_count = 0

    async def expensive_fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return {"result": "data_xyz", "counter": call_count}

    tasks = [coalescer.execute("resource_key_1", expensive_fetch) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # All 20 tasks receive the identical result
    assert len(results) == 20
    assert all(r["result"] == "data_xyz" for r in results)
    # The expensive fetch function was only called EXACTLY ONCE
    assert call_count == 1
    assert coalescer.total_requests == 20
    assert coalescer.coalesced_requests == 19


@pytest.mark.asyncio
async def test_broadcast_resolver_with_fake_server():
    server = FakeYouTubeServer()
    server.register_video(
        video_id="live_broadcast_vid_1",
        channel_id="UC_CHAN_1",
        live_chat_id="chat_bcast_1",
        is_live=True,
        title="Live Broadcast Test",
    )

    from app.youtube.client import YouTubeClient

    client = YouTubeClient()

    async def mocked_request(
        endpoint,
        params,
        method_name="videos.list",
        quota_cost=None,
        http_method="GET",
        json_data=None,
        **kwargs,
    ):
        import httpx

        url = f"https://www.googleapis.com/youtube/v3/{endpoint}"
        req = httpx.Request(http_method, url, params=params)
        resp = server.handle_request(req)
        return resp.json()

    client._request = mocked_request

    resolver = YouTubeBroadcastResolver(youtube_client=client)
    broadcast = await resolver.resolve_broadcast("live_broadcast_vid_1")

    assert broadcast.video_id == "live_broadcast_vid_1"
    assert broadcast.channel_id == "UC_CHAN_1"
    assert broadcast.live_chat_id == "chat_bcast_1"
    assert broadcast.is_live is True


@pytest.mark.asyncio
async def test_checkpoint_repository_crud(db_session: AsyncSession):
    # 1. Create creator and stream session
    c_repo = CreatorRepository(db_session)
    creator = await c_repo.create(
        youtube_channel_id="UC_CP_TEST", channel_name="CP Tester", enabled=True
    )

    s_repo = StreamRepository(db_session)
    stream = await s_repo.create(
        creator_id=creator.id,
        youtube_video_id="v_cp_1",
        youtube_live_chat_id="chat_cp_1",
        status=StreamStatus.ACTIVE.value,
    )

    # 2. Save checkpoint
    cp_repo = CheckpointRepository(db_session)
    cp1 = await cp_repo.save_checkpoint(
        stream_session_id=stream.id,
        last_next_page_token="token_p1",
        last_message_id="msg_001",
        messages_added=5,
    )
    assert cp1.stream_session_id == stream.id
    assert cp1.last_next_page_token == "token_p1"
    assert cp1.total_messages_ingested == 5

    # 3. Update existing checkpoint
    cp2 = await cp_repo.save_checkpoint(
        stream_session_id=stream.id,
        last_next_page_token="token_p2",
        last_message_id="msg_002",
        messages_added=3,
    )
    assert cp2.id == cp1.id
    assert cp2.last_next_page_token == "token_p2"
    assert cp2.total_messages_ingested == 8


@pytest.mark.asyncio
async def test_discovery_repo_crud(db_session: AsyncSession):
    d_repo = DiscoveryRepository(db_session)
    evt = await d_repo.record_event(
        channel_id="UC_DISC_1",
        video_id="v_disc_1",
        dedupe_hash="hash_disc_123",
        event_type="WEBSUB_NOTIFICATION",
        payload={"title": "Test Title"},
    )
    assert evt.id is not None
    assert evt.processed is False

    unprocessed = await d_repo.list_unprocessed()
    assert any(e.id == evt.id for e in unprocessed)

    marked = await d_repo.mark_processed(evt.id)
    assert marked is not None
    assert marked.processed is True

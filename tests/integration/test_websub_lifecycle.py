"""Integration tests for WebSub subscription, webhook verification, and Atom notifications."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.websub_subscription import WebSubStatus, WebSubSubscription
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.websub_repo import WebSubRepository

SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <link rel="hub" href="https://pubsubhubbub.appspot.com"/>
  <title>YouTube video feed</title>
  <entry>
    <id>yt:video:test_websub_vid_1</id>
    <yt:videoId>test_websub_vid_1</yt:videoId>
    <yt:channelId>UC_WEBSUB_CHAN_1</yt:channelId>
    <title>WebSub Stream Live Now</title>
    <published>2026-09-02T12:00:00+00:00</published>
    <updated>2026-09-02T12:00:00+00:00</updated>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_websub_verification_and_notification(client: AsyncClient, db_session: AsyncSession):
    # 1. Register creator and pending WebSub subscription
    c_repo = CreatorRepository(db_session)
    creator = await c_repo.create(
        youtube_channel_id="UC_WEBSUB_CHAN_1",
        channel_name="WebSub Creator",
        enabled=True,
    )

    w_repo = WebSubRepository(db_session)
    sub = WebSubSubscription(
        creator_id=creator.id,
        channel_id=creator.youtube_channel_id,
        topic_url=f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={creator.youtube_channel_id}",
        callback_url="http://test/webhooks/youtube/websub",
        status=WebSubStatus.PENDING.value,
    )
    await w_repo.create(sub)

    # 2. Test GET verification challenge
    verify_params = {
        "hub.mode": "subscribe",
        "hub.topic": sub.topic_url,
        "hub.challenge": "challenge_token_xyz_123",
        "hub.lease_seconds": "864000",
    }
    v_resp = await client.get("/webhooks/youtube/websub", params=verify_params)
    assert v_resp.status_code == 200
    assert v_resp.text == "challenge_token_xyz_123"

    # Verify DB status updated to ACTIVE
    updated_sub = await w_repo.get_by_channel_id(creator.youtube_channel_id)
    assert updated_sub is not None
    assert updated_sub.status == WebSubStatus.ACTIVE.value

    # 3. Test POST notification (first time -> received & processed)
    headers = {"Content-Type": "application/atom+xml"}
    p_resp = await client.post(
        "/webhooks/youtube/websub", content=SAMPLE_ATOM_FEED.encode(), headers=headers
    )
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert p_data["status"] == "received"
    assert p_data["deduplicated"] is False
    assert p_data["video_id"] == "test_websub_vid_1"

    # 4. Test POST duplicate notification -> received & deduplicated
    p_resp_dup = await client.post(
        "/webhooks/youtube/websub", content=SAMPLE_ATOM_FEED.encode(), headers=headers
    )
    assert p_resp_dup.status_code == 200
    assert p_resp_dup.json()["deduplicated"] is True


@pytest.mark.asyncio
async def test_creator_websub_api_endpoints(
    client: AsyncClient, db_session: AsyncSession, admin_headers: dict[str, str]
):
    c_repo = CreatorRepository(db_session)
    creator = await c_repo.create(
        youtube_channel_id="UC_API_SUB_CHAN",
        channel_name="API Sub Creator",
        enabled=True,
    )

    # Subscribe endpoint (routes through WebSubSubscriptionManager)
    # Note: We expect 200 or 502/ExternalServiceError if google hub unreachable in unit test
    sub_resp = await client.post(f"/creators/{creator.id}/websub/subscribe", headers=admin_headers)
    assert sub_resp.status_code in (200, 502)

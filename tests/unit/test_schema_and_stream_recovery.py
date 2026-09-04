"""Unit tests verifying schema reconciliation, YouTubeAPIError compatibility, and stream recovery."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError, YouTubeAPIError
from app.db.models.creator import Creator
from app.db.models.moderation_review import ModerationReview
from app.youtube.models import ResolvedBroadcast
from app.youtube.url_resolver import YouTubeUrlResolver


def test_youtube_api_error_accepts_reason_and_kwargs():
    """Verify YouTubeAPIError accepts reason, status_code, details, and arbitrary kwargs without TypeError."""
    err = YouTubeAPIError(
        message="YouTube API error (404 videoNotFound): The video cannot be found.",
        status_code=404,
        reason="videoNotFound",
        details={"endpoint": "videos", "params": {"id": "xAyGw-zB0C8"}},
        extra_info="debug_data",
    )
    assert err.status_code == 404
    assert err.reason == "videoNotFound"
    assert "videoNotFound" in err.message
    assert err.details.get("reason") == "videoNotFound"
    assert err.details.get("extra_info") == "debug_data"


def test_youtube_url_resolver_with_live_url_and_query_params():
    """Verify URL resolver extracts 11-char ID from /live/ URL with ?si= tracking query."""
    resolved = YouTubeUrlResolver.resolve_video_id(
        "https://www.youtube.com/live/xAyGw-zB0C8?si=_fQA2OXSdv"
    )
    assert resolved.video_id == "xAyGw-zB0C8"
    assert resolved.source_format == "live"
    assert resolved.normalized_url == "https://www.youtube.com/watch?v=xAyGw-zB0C8"


@pytest.mark.asyncio
async def test_manual_connect_auto_provisions_creator(
    client: AsyncClient, db_session: AsyncSession
):
    """Verify manual_connect_stream auto-creates default creator if none exists in DB."""
    # Ensure no creators exist
    await db_session.execute(text("DELETE FROM creators"))
    await db_session.flush()

    with patch("app.workers.manager.WorkerManager.start_session", new_callable=AsyncMock):
        res = await client.post(
            "/api/v1/dashboard/streams/manual-connect",
            headers={"X-Admin-Secret": "test-admin-secret-12345"},
            json={"url_or_video_id": "https://www.youtube.com/live/xAyGw-zB0C8?si=_fQA2OXSdv"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACTIVE"
        assert data["video_id"] == "xAyGw-zB0C8"


@pytest.mark.asyncio
async def test_manual_connect_handles_video_not_found_cleanly(client: AsyncClient):
    """Verify manual_connect_stream returns clean 404 detail if broadcast resolution fails with EntityNotFoundError."""
    with patch(
        "app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast",
        side_effect=EntityNotFoundError("YouTubeVideo", "nonexistent11"),
    ):
        res = await client.post(
            "/api/v1/dashboard/streams/manual-connect",
            headers={"X-Admin-Secret": "test-admin-secret-12345"},
            json={"url_or_video_id": "nonexistent11"},
        )
        assert res.status_code == 404
        data = res.json()
        assert "was not found" in data["detail"]


@pytest.mark.asyncio
async def test_manual_connect_handles_stream_not_live(client: AsyncClient):
    """Verify manual_connect_stream returns clean 400 detail if video is not live."""
    mock_broadcast = ResolvedBroadcast(
        video_id="notlive11111",
        channel_id="UC_test",
        title="Recorded Video",
        description="",
        is_live=False,
        is_upcoming=False,
        is_completed=True,
    )
    with patch(
        "app.youtube.broadcast_resolver.YouTubeBroadcastResolver.resolve_broadcast",
        return_value=mock_broadcast,
    ):
        res = await client.post(
            "/api/v1/dashboard/streams/manual-connect",
            headers={"X-Admin-Secret": "test-admin-secret-12345"},
            json={"url_or_video_id": "notlive11111"},
        )
        assert res.status_code == 400
        data = res.json()
        assert "not currently an active live stream" in data["detail"]


@pytest.mark.asyncio
async def test_moderation_queue_attribute_safety_and_serialization(
    client: AsyncClient, db_session: AsyncSession
):
    """Verify /moderation endpoint safely extracts attributes without AttributeError."""
    creator = Creator(
        id="c-mod-test",
        youtube_channel_id="UC_mod_test",
        channel_name="Moderation Tester",
    )
    db_session.add(creator)
    await db_session.flush()

    from datetime import UTC, datetime, timedelta

    from app.db.models.stream_session import StreamSession

    session = StreamSession(
        id="s-mod-test",
        creator_id=creator.id,
        youtube_video_id="video1234567",
        status="ACTIVE",
    )
    db_session.add(session)
    await db_session.flush()

    review = ModerationReview(
        id="rev-test-1",
        creator_id=creator.id,
        stream_session_id=session.id,
        message_id="msg-1",
        author_channel_id="UC_viewer_1",
        author_display_name="TrollUser",
        message_text="Inappropriate comment",
        status="PENDING",
        confidence=85,
        severity=90,
        risk_score=90,
        recommended_action="TIMEOUT",
        reason_code="HARASSMENT",
        reason="Detected offensive language",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(review)
    await db_session.flush()

    res = await client.get(
        "/api/v1/dashboard/moderation?status_filter=PENDING",
        headers={"X-Admin-Secret": "test-admin-secret-12345"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == "rev-test-1"
    assert item["author_display_name"] == "TrollUser"
    assert item["viewer_name"] == "TrollUser"
    assert item["message_text"] == "Inappropriate comment"
    assert item["confidence"] == 85
    assert item["severity"] == 90

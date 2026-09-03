"""Integration tests for manual stream connection workflow."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator


@pytest.mark.asyncio
async def test_manual_connect_duplicate_rejected(client: AsyncClient, db_session: AsyncSession):
    """Verify manual stream connect prevents duplicate active connections on the same video."""
    creator = Creator(
        id="c-conn-dup",
        youtube_channel_id="UC_conn_dup",
        channel_name="Connection Test",
    )
    db_session.add(creator)
    await db_session.commit()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}
    payload = {"url_or_video_id": "vid_dup_test_123", "creator_id": creator.id}

    # 1. First connection succeeds
    res1 = await client.post(
        "/api/v1/dashboard/streams/manual-connect",
        headers=headers,
        json=payload,
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "ACTIVE"

    # 2. Duplicate connection returns 409 Conflict
    res2 = await client.post(
        "/api/v1/dashboard/streams/manual-connect",
        headers=headers,
        json=payload,
    )
    assert res2.status_code == 409
    assert "already actively connected" in res2.json()["detail"].lower()

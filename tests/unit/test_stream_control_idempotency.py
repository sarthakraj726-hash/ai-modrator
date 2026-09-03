"""Unit tests for idempotent stream control operations and audit trail."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus


@pytest.mark.asyncio
async def test_stream_control_idempotent_disconnect(client: AsyncClient, db_session: AsyncSession):
    """Verify disconnecting an already-ended stream is strictly idempotent and auditable."""
    creator = Creator(
        id="c-ctrl-idem",
        youtube_channel_id="UC_ctrl_idem",
        channel_name="Idempotent Streamer",
    )
    db_session.add(creator)
    await db_session.flush()

    session_obj = StreamSession(
        id="sess-ctrl-idem",
        creator_id=creator.id,
        youtube_video_id="v_ctrl_idem",
        youtube_live_chat_id="chat_idem",
        status=StreamStatus.ACTIVE.value,
    )
    db_session.add(session_obj)
    await db_session.commit()

    headers = {"X-Admin-Secret": "test-admin-secret-12345"}

    # 1. First Disconnect Call
    res1 = await client.post(
        f"/api/v1/dashboard/streams/{session_obj.id}/control",
        headers=headers,
        json={"action": "disconnect", "operation_id": "op-idem-001"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "DISCONNECTED"

    # 2. Second Disconnect Call (Idempotent replay)
    res2 = await client.post(
        f"/api/v1/dashboard/streams/{session_obj.id}/control",
        headers=headers,
        json={"action": "disconnect", "operation_id": "op-idem-001"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "DISCONNECTED"
    assert "already ended" in res2.json().get("message", "").lower()

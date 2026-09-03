"""Integration tests for event-driven SSE Broadcaster."""

import asyncio

import pytest

from app.api.sse import SSEBroadcaster
from app.events.schemas import BaseEvent


@pytest.mark.asyncio
async def test_sse_broadcaster_event_delivery_and_cleanup():
    """Verify SSEBroadcaster registers client, fans out events, and cleans up on disconnect."""
    broadcaster = SSEBroadcaster(max_buffer_per_client=10, heartbeat_interval=0.2)

    client_id, q = await broadcaster.register_client()
    assert broadcaster.get_active_client_count() == 1

    # Fan out a test event
    test_event = BaseEvent(
        event_type="TestSSEEvent",
        creator_id="c-sse-1",
        payload={"data": "realtime_update"},
    )
    await broadcaster._handle_event(test_event)

    msg = await asyncio.wait_for(q.get(), timeout=1.0)
    assert msg["event"] == "TestSSEEvent"
    assert msg["creator_id"] == "c-sse-1"

    # Clean up client
    await broadcaster.unregister_client(client_id)
    assert broadcaster.get_active_client_count() == 0

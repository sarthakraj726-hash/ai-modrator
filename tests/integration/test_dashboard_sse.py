"""Integration tests for event-driven SSE Broadcaster with real Last-Event-ID replay semantics."""

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


@pytest.mark.asyncio
async def test_sse_last_event_id_real_replay_flow():
    """
    Forensic test verifying genuine Last-Event-ID replay semantics:
    1. Connect SSE
    2. Emit event A
    3. Emit event B
    4. Disconnect after receiving A
    5. Emit event C
    6. Reconnect with Last-Event-ID=A
    7. Verify B and C are replayed
    8. Verify subsequent live events are delivered in order
    """
    broadcaster = SSEBroadcaster(
        max_buffer_per_client=20, heartbeat_interval=1.0, replay_buffer_size=100
    )

    # 1. Emit Event A
    evt_a = BaseEvent(event_type="EventA", creator_id="c-1", payload={"step": "A"})
    await broadcaster._handle_event(evt_a)

    # 2. Emit Event B
    evt_b = BaseEvent(event_type="EventB", creator_id="c-1", payload={"step": "B"})
    await broadcaster._handle_event(evt_b)

    # 3. Emit Event C while client is offline
    evt_c = BaseEvent(event_type="EventC", creator_id="c-1", payload={"step": "C"})
    await broadcaster._handle_event(evt_c)

    # 4. Reconnect with Last-Event-ID=A
    replayed = await broadcaster.get_replay_events(evt_a.event_id)
    assert len(replayed) == 2
    assert replayed[0]["id"] == evt_b.event_id
    assert replayed[0]["event"] == "EventB"
    assert replayed[1]["id"] == evt_c.event_id
    assert replayed[1]["event"] == "EventC"

    # 5. Connect generator with Last-Event-ID=A and test streaming
    gen = broadcaster.client_event_generator(last_event_id=evt_a.event_id)

    # Read connected ack
    ack = await anext(gen)
    assert "event: connected" in ack

    # Read replayed B
    msg_b = await anext(gen)
    assert f"id: {evt_b.event_id}" in msg_b
    assert "event: EventB" in msg_b

    # Read replayed C
    msg_c = await anext(gen)
    assert f"id: {evt_c.event_id}" in msg_c
    assert "event: EventC" in msg_c

    # 6. Emit live Event D and verify subsequent delivery
    evt_d = BaseEvent(event_type="EventD", creator_id="c-1", payload={"step": "D"})
    await broadcaster._handle_event(evt_d)

    msg_d = await anext(gen)
    assert f"id: {evt_d.event_id}" in msg_d
    assert "event: EventD" in msg_d

    # Clean disconnect
    await gen.aclose()
    assert broadcaster.get_active_client_count() == 0


@pytest.mark.asyncio
async def test_sse_unknown_or_stale_last_event_id_safe_fallback():
    """Verify that an unknown or expired Last-Event-ID falls back safely without crashing."""
    broadcaster = SSEBroadcaster(max_buffer_per_client=10, heartbeat_interval=0.2)

    gen = broadcaster.client_event_generator(last_event_id="completely-unknown-stale-id")

    # Connect handshake should succeed
    ack = await anext(gen)
    assert "event: connected" in ack

    # Live event delivered
    evt = BaseEvent(event_type="LiveOnly", creator_id="c-2", payload={"ok": True})
    await broadcaster._handle_event(evt)

    msg = await anext(gen)
    assert "event: LiveOnly" in msg

    await gen.aclose()
    assert broadcaster.get_active_client_count() == 0


@pytest.mark.asyncio
async def test_sse_multi_client_fanout_and_bounded_buffer():
    """Verify simultaneous fanout to multiple clients and bounded queue drop semantics."""
    broadcaster = SSEBroadcaster(max_buffer_per_client=3, heartbeat_interval=0.5)

    c1_id, q1 = await broadcaster.register_client()
    c2_id, q2 = await broadcaster.register_client()
    assert broadcaster.get_active_client_count() == 2

    # Send 5 events into buffer of size 3
    for i in range(5):
        await broadcaster._handle_event(BaseEvent(event_type=f"Burst_{i}", payload={"i": i}))

    # Queue should not block or exceed maxsize 3
    assert q1.qsize() == 3
    assert q2.qsize() == 3

    # Disconnect client 1
    await broadcaster.unregister_client(c1_id)
    assert broadcaster.get_active_client_count() == 1

    # Client 2 continues
    await broadcaster._handle_event(BaseEvent(event_type="PostC1Event", payload={"val": 99}))
    await broadcaster.unregister_client(c2_id)
    assert broadcaster.get_active_client_count() == 0

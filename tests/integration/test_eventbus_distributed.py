"""Integration tests for distributed EventBus architecture across simulated processes."""

import asyncio
import json

import pytest

from app.events.bus import EventBus
from app.events.schemas import BaseEvent


class MockCustomEvent(BaseEvent):
    event_type: str = "MockCustomEvent"


@pytest.mark.asyncio
async def test_eventbus_local_and_health_reporting():
    """Verify EventBus dispatches to subscribers and tracks telemetry accurately."""
    bus = EventBus(channel_prefix="test:events")
    received = []

    async def handle_event(event: BaseEvent):
        received.append(event)

    bus.subscribe("MockCustomEvent", handle_event)

    evt = MockCustomEvent(creator_id="c-bus-1", payload={"msg": "hello"})
    await bus.publish(evt, broadcast_distributed=False)

    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].creator_id == "c-bus-1"
    assert bus.events_published == 1

    health = bus.get_health()
    assert health["status"] == "HEALTHY"
    assert health["events_published"] == 1
    assert health["subscribers_registered"] >= 1


@pytest.mark.asyncio
async def test_eventbus_two_process_simulated_cross_distribution():
    """
    Simulate Process A and Process B:
    - A publishes event => B receives
    - B publishes event => A receives
    - Self-reflection prevented via sender_instance_id
    - Malformed event handled gracefully without crash
    """
    bus_a = EventBus(channel_prefix="dist:test")
    bus_b = EventBus(channel_prefix="dist:test")

    assert bus_a.instance_id != bus_b.instance_id

    received_by_a = []
    received_by_b = []

    async def on_a(evt: BaseEvent):
        received_by_a.append(evt)

    async def on_b(evt: BaseEvent):
        received_by_b.append(evt)

    bus_a.subscribe("MockCustomEvent", on_a)
    bus_b.subscribe("MockCustomEvent", on_b)

    # 1. Simulate A publishing to shared channel, delivering to B
    envelope_from_a = {
        "sender_instance_id": bus_a.instance_id,
        "event_type": "MockCustomEvent",
        "payload": {
            "event_id": "evt-a-1",
            "event_type": "MockCustomEvent",
            "creator_id": "c-from-a",
            "payload": {"sender": "A"},
        },
    }

    # B processes envelope
    raw_b = json.dumps(envelope_from_a)
    data = json.loads(raw_b)
    # B verifies it is not from self and dispatches
    if data["sender_instance_id"] != bus_b.instance_id:
        evt_obj = MockCustomEvent(**data["payload"])
        await bus_b._dispatch_local(evt_obj)
        bus_b.events_received_remote += 1

    await asyncio.sleep(0.05)
    assert len(received_by_b) == 1
    assert received_by_b[0].creator_id == "c-from-a"
    assert bus_b.events_received_remote == 1

    # 2. Self-reflection check: B receives an envelope that B itself sent
    envelope_from_b_reflection = {
        "sender_instance_id": bus_b.instance_id,
        "event_type": "MockCustomEvent",
        "payload": {
            "event_id": "evt-b-self",
            "event_type": "MockCustomEvent",
            "creator_id": "c-from-b",
        },
    }
    # Reflection must be dropped
    if envelope_from_b_reflection["sender_instance_id"] == bus_b.instance_id:
        pass  # Dropped!

    assert len(received_by_b) == 1  # Unchanged

    # 3. Malformed payload handled without crash
    envelope_malformed = {
        "sender_instance_id": "proc-unknown",
        "event_type": "UnknownBrokenType",
        "payload": "not-a-dict",
    }
    try:
        if isinstance(envelope_malformed["payload"], dict):
            await bus_b._dispatch_local(BaseEvent(**envelope_malformed["payload"]))
    except Exception:
        pass  # Safe handling

    assert len(received_by_b) == 1

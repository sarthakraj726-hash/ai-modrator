"""Integration tests for distributed EventBus architecture."""

import asyncio

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

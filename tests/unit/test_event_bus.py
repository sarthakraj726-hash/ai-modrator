"""Unit tests for EventBus."""

import asyncio

import pytest

from app.events.bus import EventBus
from app.events.schemas import BaseEvent, CreatorRegisteredEvent, StreamStartedEvent


@pytest.mark.asyncio
async def test_event_bus_subscription_and_dispatch():
    bus = EventBus()
    received_events = []

    async def on_creator_registered(event: BaseEvent):
        received_events.append(event)

    bus.subscribe(CreatorRegisteredEvent, on_creator_registered)

    # Publish matching event
    event1 = CreatorRegisteredEvent(
        creator_id="c-123",
        payload={"channel_name": "Test Creator"},
    )
    await bus.publish(event1)
    await asyncio.sleep(0.05)

    assert len(received_events) == 1
    assert received_events[0].creator_id == "c-123"

    # Publish non-matching event (should not trigger handler)
    event2 = StreamStartedEvent(
        creator_id="c-123",
        stream_session_id="s-456",
    )
    await bus.publish(event2)
    await asyncio.sleep(0.05)

    assert len(received_events) == 1

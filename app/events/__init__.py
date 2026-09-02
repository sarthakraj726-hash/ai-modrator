"""Event-driven messaging and pub/sub architecture."""

from app.events.bus import EventBus, get_event_bus
from app.events.schemas import (
    BaseEvent,
    CreatorRegisteredEvent,
    CreatorUpdatedEvent,
    StreamConnectedEvent,
    StreamConnectRequestedEvent,
    StreamDisconnectedEvent,
    StreamEndedEvent,
    StreamErrorEvent,
    StreamStartedEvent,
    SystemCriticalEvent,
    SystemErrorEvent,
    SystemWarningEvent,
)

__all__ = [
    "BaseEvent",
    "CreatorRegisteredEvent",
    "CreatorUpdatedEvent",
    "StreamConnectRequestedEvent",
    "StreamConnectedEvent",
    "StreamDisconnectedEvent",
    "StreamStartedEvent",
    "StreamEndedEvent",
    "StreamErrorEvent",
    "SystemWarningEvent",
    "SystemErrorEvent",
    "SystemCriticalEvent",
    "EventBus",
    "get_event_bus",
]

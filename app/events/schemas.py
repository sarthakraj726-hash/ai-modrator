"""Typed Pydantic domain events."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def generate_event_id() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(UTC)


class BaseEvent(BaseModel):
    """Base schema for all domain and infrastructure events."""
    event_id: str = Field(default_factory=generate_event_id)
    event_type: str
    timestamp: datetime = Field(default_factory=get_utc_now)
    creator_id: str | None = None
    stream_session_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# Creator Events
# ==============================================================================

class CreatorRegisteredEvent(BaseEvent):
    event_type: Literal["CreatorRegistered"] = "CreatorRegistered"


class CreatorUpdatedEvent(BaseEvent):
    event_type: Literal["CreatorUpdated"] = "CreatorUpdated"


# ==============================================================================
# Stream Lifecycle Events
# ==============================================================================

class StreamConnectRequestedEvent(BaseEvent):
    event_type: Literal["StreamConnectRequested"] = "StreamConnectRequested"


class StreamConnectedEvent(BaseEvent):
    event_type: Literal["StreamConnected"] = "StreamConnected"


class StreamDisconnectedEvent(BaseEvent):
    event_type: Literal["StreamDisconnected"] = "StreamDisconnected"


class StreamStartedEvent(BaseEvent):
    event_type: Literal["StreamStarted"] = "StreamStarted"


class StreamEndedEvent(BaseEvent):
    event_type: Literal["StreamEnded"] = "StreamEnded"


class StreamErrorEvent(BaseEvent):
    event_type: Literal["StreamError"] = "StreamError"


# ==============================================================================
# System Health & Alert Events
# ==============================================================================

class SystemWarningEvent(BaseEvent):
    event_type: Literal["SystemWarning"] = "SystemWarning"


class SystemErrorEvent(BaseEvent):
    event_type: Literal["SystemError"] = "SystemError"


class SystemCriticalEvent(BaseEvent):
    event_type: Literal["SystemCritical"] = "SystemCritical"

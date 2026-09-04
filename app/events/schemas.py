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
# Phase 2: YouTube Discovery & Chat Events
# ==============================================================================


class YouTubeWebSubNotificationEvent(BaseEvent):
    event_type: Literal["YouTubeWebSubNotification"] = "YouTubeWebSubNotification"
    channel_id: str = ""
    video_id: str = ""
    title: str = ""
    dedupe_hash: str = ""


class ChatMessageReceivedEvent(BaseEvent):
    event_type: Literal["ChatMessageReceived"] = "ChatMessageReceived"
    message_id: str = ""
    channel_id: str = ""
    video_id: str = ""
    live_chat_id: str = ""
    author_channel_id: str = ""
    author_display_name: str = ""
    message_text: str = ""
    is_moderator: bool = False
    is_channel_owner: bool = False
    is_member: bool = False
    is_verified: bool = False
    is_bot: bool = False


class YouTubeKeyCooldownEvent(BaseEvent):
    event_type: Literal["YouTubeKeyCooldown"] = "YouTubeKeyCooldown"
    slot: str = ""
    masked_key: str = ""
    cooldown_seconds: int = 0
    reason: str = ""


class YouTubeQuotaWarningEvent(BaseEvent):
    event_type: Literal["YouTubeQuotaWarning"] = "YouTubeQuotaWarning"
    used_units: int = 0
    daily_budget: int = 4000
    percentage_used: float = 0.0


# ==============================================================================
# System Health & Alert Events
# ==============================================================================


class SystemWarningEvent(BaseEvent):
    event_type: Literal["SystemWarning"] = "SystemWarning"


class SystemErrorEvent(BaseEvent):
    event_type: Literal["SystemError"] = "SystemError"


class SystemCriticalEvent(BaseEvent):
    event_type: Literal["SystemCritical"] = "SystemCritical"


EVENT_TYPE_MAP: dict[str, type[BaseEvent]] = {
    "CreatorRegistered": CreatorRegisteredEvent,
    "CreatorUpdated": CreatorUpdatedEvent,
    "StreamConnectRequested": StreamConnectRequestedEvent,
    "StreamConnected": StreamConnectedEvent,
    "StreamDisconnected": StreamDisconnectedEvent,
    "StreamStarted": StreamStartedEvent,
    "StreamEnded": StreamEndedEvent,
    "StreamError": StreamErrorEvent,
    "ChatMessageReceived": ChatMessageReceivedEvent,
    "YouTubeKeyCooldown": YouTubeKeyCooldownEvent,
    "YouTubeQuotaWarning": YouTubeQuotaWarningEvent,
    "SystemWarning": SystemWarningEvent,
    "SystemError": SystemErrorEvent,
    "SystemCritical": SystemCriticalEvent,
}

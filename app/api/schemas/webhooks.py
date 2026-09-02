"""Pydantic schemas for WebSub and webhook endpoints."""

from datetime import datetime

from pydantic import BaseModel


class WebSubSubscriptionResponse(BaseModel):
    id: str
    creator_id: str
    channel_id: str
    topic_url: str
    callback_url: str
    status: str
    lease_seconds: int
    lease_expires_at: datetime | None = None
    last_subscribed_at: datetime | None = None
    last_verified_at: datetime | None = None
    last_notification_at: datetime | None = None
    failure_count: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class WebSubNotificationAck(BaseModel):
    status: str = "received"
    channel_id: str
    video_id: str
    deduplicated: bool = False
    discovery_event_id: str | None = None

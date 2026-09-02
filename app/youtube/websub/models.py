"""Data models for WebSub notifications and subscriptions."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class WebSubNotification(BaseModel):
    """Structured notification extracted from YouTube WebSub Atom feed."""

    channel_id: str
    video_id: str
    title: str = ""
    published_at: datetime | None = None
    updated_at: datetime | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dedupe_hash: str
    topic_url: str = ""
    feed_id: str = ""


class WebSubSubscriptionRequest(BaseModel):
    """Parameters for sending subscription request to PubSubHubbub hub."""

    creator_id: str
    channel_id: str
    callback_url: str
    hub_url: str = "https://pubsubhubbub.appspot.com/subscribe"
    mode: str = "subscribe"
    lease_seconds: int = 864000  # 10 days

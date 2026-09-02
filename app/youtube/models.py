"""Domain schemas and data transfer objects for YouTube integration."""

from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class QuotaCost(IntEnum):
    """Standard YouTube Data API v3 quota costs in units."""
    VIDEOS_LIST = 1
    CHANNELS_LIST = 1
    LIVE_BROADCASTS_LIST = 1
    LIVE_CHAT_LIST = 1
    LIVE_CHAT_INSERT = 50
    LIVE_CHAT_DELETE = 50
    LIVE_CHAT_BAN = 50
    SEARCH_LIST = 100


class YouTubeAuthor(BaseModel):
    """YouTube chat author profile."""
    channel_id: str
    channel_url: str = ""
    display_name: str
    profile_image_url: str = ""
    is_chat_owner: bool = False
    is_chat_sponsor: bool = False
    is_chat_moderator: bool = False
    is_verified: bool = False


class YouTubeChatMessage(BaseModel):
    """Normalized live chat message."""
    message_id: str
    live_chat_id: str
    author: YouTubeAuthor
    display_message: str
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_type: str = "textMessageEvent"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class YouTubeChatPage(BaseModel):
    """Page of live chat messages from YouTube API."""
    messages: list[YouTubeChatMessage] = Field(default_factory=list)
    next_page_token: str | None = None
    polling_interval_millis: int = 4000
    offline_at: datetime | None = None


class YouTubeStreamInfo(BaseModel):
    """Metadata regarding a YouTube live stream broadcast."""
    video_id: str
    channel_id: str
    title: str = ""
    description: str = ""
    live_chat_id: str | None = None
    is_live: bool = False
    actual_start_time: datetime | None = None
    concurrent_viewers: int | None = None

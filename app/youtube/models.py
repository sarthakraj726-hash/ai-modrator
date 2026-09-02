"""Domain schemas and data transfer objects for YouTube integration."""

from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, Field


class QuotaCost(IntEnum):
    """Standard YouTube Data API v3 quota costs in units."""

    VIDEOS_LIST = 1
    CHANNELS_LIST = 1
    LIVE_BROADCASTS_LIST = 1
    LIVE_CHAT_LIST = 1
    LIVE_CHAT_STREAM_LIST = 1
    LIVE_CHAT_INSERT = 50
    LIVE_CHAT_DELETE = 50
    LIVE_CHAT_BAN = 50
    SEARCH_LIST = 100


class RequestClassification(str, Enum):
    """Classification of network and API request results for quota & retry."""

    SUCCESS = "SUCCESS"
    REQUEST_NOT_SENT = "REQUEST_NOT_SENT"
    REQUEST_SENT_NETWORK_FAILURE = "REQUEST_SENT_NETWORK_FAILURE"
    HTTP_400 = "HTTP_400"
    HTTP_401 = "HTTP_401"
    HTTP_403 = "HTTP_403"
    HTTP_404 = "HTTP_404"
    HTTP_409 = "HTTP_409"
    HTTP_429 = "HTTP_429"
    HTTP_500 = "HTTP_500"
    HTTP_502 = "HTTP_502"
    HTTP_503 = "HTTP_503"
    HTTP_504 = "HTTP_504"


class YouTubeAPIError(Exception):
    """Structured classification for YouTube API and network errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        reason: str | None = None,
        domain: str | None = None,
        classification: RequestClassification = RequestClassification.REQUEST_NOT_SENT,
        retryable: bool = False,
        key_related: bool = False,
        quota_related: bool = False,
        resource_missing: bool = False,
        stream_ended: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.reason = reason
        self.domain = domain
        self.classification = classification
        self.retryable = retryable
        self.key_related = key_related
        self.quota_related = quota_related
        self.resource_missing = resource_missing
        self.stream_ended = stream_ended

    def __repr__(self) -> str:
        return (
            f"<YouTubeAPIError(status={self.status_code}, reason='{self.reason}', "
            f"class={self.classification.value}, retryable={self.retryable})>"
        )


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
    """Normalized live chat message with explicit stream routing."""

    event_id: str = ""
    message_id: str
    stream_session_id: str = ""
    creator_id: str = ""
    channel_id: str = ""
    video_id: str = ""
    live_chat_id: str
    author: YouTubeAuthor
    display_message: str
    message_text: str = ""
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_type: str = "textMessageEvent"
    is_moderator: bool = False
    is_channel_owner: bool = False
    is_member: bool = False
    is_verified: bool = False
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.message_text:
            self.message_text = self.display_message
        if not self.event_id:
            self.event_id = f"evt_{self.message_id}"
        self.is_moderator = self.author.is_chat_moderator
        self.is_channel_owner = self.author.is_chat_owner
        self.is_member = self.author.is_chat_sponsor
        self.is_verified = self.author.is_verified


class YouTubeChatPage(BaseModel):
    """Page of live chat messages from YouTube API."""

    messages: list[YouTubeChatMessage] = Field(default_factory=list)
    next_page_token: str | None = None
    polling_interval_millis: int = 4000
    offline_at: datetime | None = None


class ResolvedYouTubeUrl(BaseModel):
    """Structured resolution output for YouTube URLs."""

    original_url: str
    normalized_url: str
    video_id: str
    source_format: str  # e.g., "watch", "live", "shortlink", "direct_id"


class ResolvedChannel(BaseModel):
    """Structured resolution output for YouTube Channel identifiers."""

    channel_id: str
    channel_name: str = ""
    handle: str | None = None
    custom_url: str | None = None
    source_format: str = "channel_id"


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


class ResolvedBroadcast(BaseModel):
    """Authoritative metadata resolved for a YouTube live broadcast."""

    video_id: str
    channel_id: str
    channel_title: str = ""
    title: str = ""
    description: str = ""
    live_chat_id: str | None = None
    is_live: bool = False
    is_upcoming: bool = False
    is_completed: bool = False
    scheduled_start_time: datetime | None = None
    actual_start_time: datetime | None = None
    concurrent_viewers: int | None = None
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

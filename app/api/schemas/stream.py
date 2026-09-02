"""Stream session request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class StreamConnectRequest(BaseModel):
    youtube_live_url: str | None = Field(
        None,
        description="YouTube live stream URL (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)",
    )
    creator_id: str | None = Field(None, description="Optional ID of registered creator")
    youtube_video_id: str | None = Field(
        None, min_length=3, max_length=64, description="Optional direct YouTube Video ID"
    )
    youtube_live_chat_id: str | None = Field(None, description="Optional live chat ID")


class StreamSessionResponse(BaseModel):
    id: str
    creator_id: str
    youtube_video_id: str
    youtube_live_chat_id: str | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

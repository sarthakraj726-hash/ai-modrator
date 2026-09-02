"""Stream session request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class StreamConnectRequest(BaseModel):
    creator_id: str = Field(..., description="ID of registered creator")
    youtube_video_id: str = Field(..., min_length=3, max_length=64, description="YouTube Video ID")
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

"""Creator request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CreatorCreate(BaseModel):
    youtube_channel_id: str = Field(
        ..., min_length=3, max_length=64, description="YouTube Channel ID"
    )
    channel_name: str = Field(
        ..., min_length=1, max_length=255, description="Human-readable channel title"
    )
    enabled: bool = True


class CreatorUpdate(BaseModel):
    channel_name: str | None = Field(None, min_length=1, max_length=255)
    enabled: bool | None = None


class CreatorResponse(BaseModel):
    id: str
    youtube_channel_id: str
    channel_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

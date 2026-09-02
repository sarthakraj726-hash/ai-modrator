"""Health and diagnostic endpoint schemas."""

from typing import Any

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = "live"


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str


class YouTubeHealthInfo(BaseModel):
    quota_daily_limit: int
    quota_used: int
    quota_remaining: int
    quota_percentage_used: float
    key_pool: list[dict[str, Any]] = Field(default_factory=list)


class SystemHealthResponse(BaseModel):
    app_name: str
    app_env: str
    status: str
    dependencies: dict[str, str]
    workers: dict[str, Any]
    youtube: YouTubeHealthInfo

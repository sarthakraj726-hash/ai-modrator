"""Pydantic schemas for Moderation API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModerationReviewResponse(BaseModel):
    id: str
    creator_id: str
    stream_session_id: str
    message_id: str
    author_channel_id: str
    author_display_name: str
    message_text: str
    status: str
    risk_score: int
    confidence: int
    severity: int
    recommended_action: str
    final_action: str | None = None
    reason_code: str
    reason: str
    language: str
    context_summary: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class ReviewResolutionRequest(BaseModel):
    moderator_id: str = "creator-admin"
    override_action: str | None = None
    notes: str | None = None


class ReviewResolutionResponse(BaseModel):
    success: bool
    review_id: str
    status: str
    message: str


class CreatorPersonaUpdateRequest(BaseModel):
    persona_type: str = "CO_HOST"
    energy: int = 7
    humor: int = 8
    verbosity: int = 3
    emoji: int = 6
    roast: int = 4
    helpfulness: int = 8
    custom_system_prompt: str | None = None


class CreatorModerationPolicyUpdateRequest(BaseModel):
    moderation_strictness: str = "BALANCED"
    moderation_mode: str = "ACTIVE"
    auto_moderation_enabled: bool = True
    hitl_enabled: bool = True

"""Moderation domain schemas and progressive penalty layer definitions."""

from datetime import UTC, datetime
from enum import Enum, IntEnum

from pydantic import BaseModel, Field


class ModerationLayer(IntEnum):
    """5-Layer Progressive Enforcement Hierarchy."""

    LAYER_1_LIGHT_WARNING = 1  # Friendly public / private reminder
    LAYER_2_WARNING_AND_DELETE = 2  # Delete offending message + clear warning
    LAYER_3_SHORT_TIMEOUT = 3  # 60s - 300s timeout + direct notice
    LAYER_4_EXTENDED_TIMEOUT = 4  # 30m - 1hr extended mute
    LAYER_5_HIDE_BAN = 5  # Permanent channel block / hide user


class ModerationAction(str, Enum):
    ALLOW = "ALLOW"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    WARN = "WARN"
    DELETE = "DELETE"
    TIMEOUT = "TIMEOUT"
    BAN = "BAN"


class ModerationRule(BaseModel):
    id: str
    name: str
    pattern: str | None = None
    category: str = "general"
    severity_layer: ModerationLayer = ModerationLayer.LAYER_1_LIGHT_WARNING
    enabled: bool = True


class ModerationDecision(BaseModel):
    action: ModerationAction
    layer: ModerationLayer | None = None
    confidence_score: float = 1.0  # 0.0 to 1.0
    reason: str = "Passed moderation rules"
    matched_rules: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    suggested_timeout_seconds: int = 0
    warning_message: str | None = None


class ReviewItem(BaseModel):
    """Item queued for human-in-the-loop review."""

    item_id: str
    stream_session_id: str
    creator_id: str
    author_id: str
    author_name: str
    message_text: str
    ai_confidence: float
    detected_layer: ModerationLayer
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "PENDING"  # PENDING, APPROVED, OVERRULED

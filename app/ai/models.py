"""Data transfer schemas for LLM provider requests, structured outputs, and tool calling."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ModelTier(str, Enum):
    FAST = "FAST"
    BALANCED = "BALANCED"
    HIGH_ACCURACY = "HIGH_ACCURACY"
    REASONING = "REASONING"
    FALLBACK = "FALLBACK"


class TaskType(str, Enum):
    MODERATION_CLASSIFY = "moderation_classify"
    COHOST_REPLY = "cohost_reply"
    CONTEXT_ANALYZE = "context_analyze"
    SUMMARIZE = "summarize"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCallRequest(BaseModel):
    id: str
    function_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class CompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    model_tier: ModelTier = ModelTier.BALANCED
    task_type: TaskType = TaskType.COHOST_REPLY
    fallback_models: list[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 500
    tools: list[ToolDefinition] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompletionResponse(BaseModel):
    content: str
    model_used: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModerationAIResult(BaseModel):
    """Structured AI output schema for live-chat moderation classification."""

    category: str = Field(
        default="none",
        description="Category: none, spam, harassment, targeted_abuse, hate, sexual, threat, scam, self_promo, flood, other",
    )
    severity: int = Field(default=0, ge=0, le=100, description="Severity score from 0 to 100")
    confidence: int = Field(default=100, ge=0, le=100, description="Confidence score from 0 to 100")
    intent: str = Field(
        default="neutral",
        description="Intent: playful, neutral, hostile, provocative, unknown",
    )
    target: str = Field(
        default="none",
        description="Target: none, viewer, creator, group, other",
    )
    recommended_action: str = Field(
        default="allow",
        description="Action: allow, warn, delete, timeout, hide, review",
    )
    reason_code: str = Field(default="NORMAL_CHAT", description="Standardized reason code")
    short_reason: str = Field(
        default="Content adheres to community standards", description="Concise explanation"
    )
    language: str = Field(
        default="en", description="Detected language: en, hi, hinglish, mixed, other"
    )
    requires_human_review: bool = Field(
        default=False, description="Flag indicating human review recommendation"
    )


class CohostReplyResult(BaseModel):
    """Structured AI output schema for Honney co-host responses."""

    should_reply: bool = Field(default=False, description="Whether Honney should post this reply")
    reply_text: str = Field(default="", description="Persona-aligned response (1-2 sentences)")
    tone: str = Field(default="friendly", description="Voice tone applied")
    suggested_action: str | None = Field(
        default=None, description="Optional application action requested"
    )
    tools_requested: list[ToolCallRequest] = Field(default_factory=list)

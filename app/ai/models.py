"""Data transfer schemas for LLM provider requests and responses."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    name: str | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 500
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompletionResponse(BaseModel):
    content: str
    model_used: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    raw_response: dict[str, Any] = Field(default_factory=dict)

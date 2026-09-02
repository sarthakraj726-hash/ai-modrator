"""Command execution models and schemas."""

from typing import Any

from pydantic import BaseModel, Field

from app.core.rbac import Role
from app.youtube.models import YouTubeAuthor


class ChatCommand(BaseModel):
    name: str
    description: str = ""
    min_role: Role = Role.VIEWER
    cooldown_seconds: int = 5
    enabled: bool = True
    aliases: list[str] = Field(default_factory=list)


class CommandExecutionContext(BaseModel):
    command_name: str
    args: list[str] = Field(default_factory=list)
    raw_text: str
    creator_id: str
    stream_session_id: str
    author: YouTubeAuthor
    author_role: Role = Role.VIEWER


class CommandResult(BaseModel):
    success: bool
    response_message: str | None = None
    action_taken: str | None = None
    error_message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

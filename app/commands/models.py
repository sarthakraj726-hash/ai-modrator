"""Command execution models, schemas, and category definitions."""

from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.rbac import Role
from app.youtube.models import YouTubeAuthor


class CommandCategory(str, Enum):
    UTILITY = "UTILITY"
    SOCIAL = "SOCIAL"
    MODERATION = "MODERATION"
    ECONOMY = "ECONOMY"
    STORE = "STORE"
    XP = "XP"
    GAME = "GAME"
    ADMIN = "ADMIN"


class CommandExecutionContext(BaseModel):
    command_name: str
    args: list[str] = Field(default_factory=list)
    raw_text: str
    creator_id: str
    stream_session_id: str
    author: YouTubeAuthor
    author_role: Role = Role.VIEWER
    live_chat_id: str = ""

    class Config:
        arbitrary_types_allowed = True


class CommandResult(BaseModel):
    success: bool
    response_message: str | None = None
    action_taken: str | None = None
    error_message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


CommandHandler = Callable[[CommandExecutionContext, Any], Coroutine[Any, Any, CommandResult]]


class ChatCommand(BaseModel):
    name: str
    description: str = ""
    usage: str = ""
    category: CommandCategory = CommandCategory.UTILITY
    min_role: Role = Role.VIEWER
    cooldown_seconds: int = 5
    enabled: bool = True
    aliases: list[str] = Field(default_factory=list)
    ai_enabled: bool = False
    creator_scoped: bool = True
    public: bool = True
    handler: Any = None  # Async callback

    class Config:
        arbitrary_types_allowed = True

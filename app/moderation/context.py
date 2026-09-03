"""Enriched chat context model for token-efficient moderation and co-host inference."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HonneyChatContext(BaseModel):
    """
    Enriched, privacy-aware context model encapsulating all stream, creator,
    and user signals needed to make accurate, contextual moderation/co-host decisions.
    """

    message_id: str
    creator_id: str
    stream_session_id: str
    channel_id: str = ""
    video_id: str = ""
    author_id: str
    author_name: str
    message_text: str
    normalized_text: str = ""
    language: str = "en"
    is_member: bool = False
    is_moderator: bool = False
    is_owner: bool = False
    is_verified: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Token-optimized context window
    recent_user_messages: list[str] = Field(default_factory=list)
    recent_chat_context: list[str] = Field(default_factory=list)

    # Creator-scoped trust state
    user_trust_score: int = 50
    user_violation_count: int = 0

    # Stream environmental signals
    stream_phase: str = "LIVE"
    quiet_mode: bool = False
    creator_speaking: bool = False

    def build_prompt_context(self, max_recent: int = 3) -> str:
        """
        Build a concise, minimal-token context string for LLM prompts.
        Strictly excludes sensitive system configuration and internal secrets.
        """
        lines = [
            f"Speaker: @{self.author_name} (Trust: {self.user_trust_score}/100, Member: {self.is_member})",
            f"Language: {self.language}",
            f'Current Message: "{self.normalized_text or self.message_text}"',
        ]

        if self.recent_user_messages:
            user_history = self.recent_user_messages[-max_recent:]
            lines.append(f"Recent from user: {user_history}")

        if self.recent_chat_context:
            room_context = self.recent_chat_context[-max_recent:]
            lines.append(f"Recent chat context: {room_context}")

        return "\n".join(lines)

"""Moderation Engine abstract interface."""

from abc import ABC, abstractmethod

from app.moderation.models import ModerationDecision, ReviewItem
from app.youtube.models import YouTubeChatMessage


class ModerationEngine(ABC):
    """Abstract interface for multi-layer, Hinglish/multilingual aware moderation."""

    @abstractmethod
    async def evaluate_message(
        self,
        creator_id: str,
        message: YouTubeChatMessage,
        user_history: dict | None = None,
    ) -> ModerationDecision:
        """Evaluate a chat message against creator rules, progressive penalty history, and AI."""
        pass

    @abstractmethod
    async def queue_for_human_review(self, item: ReviewItem) -> str:
        """Submit an ambiguous high-stakes decision to human moderator review queue."""
        pass

    @abstractmethod
    async def get_pending_reviews(self, creator_id: str) -> list[ReviewItem]:
        """Fetch pending human-in-the-loop review items."""
        pass

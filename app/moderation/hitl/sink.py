"""Human-in-the-loop (HITL) notification sink interface and Discord dispatch."""

from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.db.models.moderation_review import ModerationReview
from app.discord.logger import DiscordLogger, get_discord_logger

logger = get_logger("app.moderation.hitl.sink")


class ReviewNotificationSink(ABC):
    """Abstract interface for notifying human moderators of ambiguous decisions."""

    @abstractmethod
    async def notify_review_created(self, review: ModerationReview, ttl_seconds: int = 60) -> bool:
        """Send review prompt to moderator destination."""
        pass


class DiscordReviewNotificationSink(ReviewNotificationSink):
    """
    Delivers formatted review requests to creator's designated Discord channel
    with !uk punish yes/no commands.
    """

    def __init__(self, discord_logger: DiscordLogger | None = None) -> None:
        self.discord_logger = discord_logger or get_discord_logger()

    async def notify_review_created(self, review: ModerationReview, ttl_seconds: int = 60) -> bool:
        """Post review card to Discord."""
        content = (
            f"⚖️ **[MODERATION REVIEW REQUIRED]** `ID: {review.id[:8]}`\n"
            f"**Speaker**: @{review.author_display_name} (`{review.author_channel_id}`)\n"
            f'**Message**: "{review.message_text}"\n'
            f"**Detected**: `{review.reason_code}` (Conf: {review.confidence}%, Sev: {review.severity}%)\n"
            f"**Recommended Action**: `{review.recommended_action}`\n"
            f"**Reason**: {review.reason}\n"
            f"👉 Approve: `!uk punish yes {review.id[:8]}` | Deny: `!uk punish no {review.id[:8]}`\n"
            f"⏳ *Auto-expires in {ttl_seconds}s (safe default: no action upon expiration)*"
        )

        logger.info(f"Dispatching review prompt for review {review.id[:8]} to Discord sink")
        return await self.discord_logger.log_creator_event(
            creator_id=review.creator_id,
            message=content,
            title="HITL Moderation Alert",
        )


_global_review_sink: ReviewNotificationSink | None = None


def get_review_notification_sink() -> ReviewNotificationSink:
    """Return singleton ReviewNotificationSink."""
    global _global_review_sink
    if _global_review_sink is None:
        _global_review_sink = DiscordReviewNotificationSink()
    return _global_review_sink

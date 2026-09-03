"""Human-in-the-loop review orchestration service."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models.moderation_review import ModerationReview
from app.db.repositories.feedback_repo import ModerationFeedbackRepository
from app.db.repositories.review_repo import ReviewRepository
from app.moderation.actions import YouTubeModerationActionService, get_action_service
from app.moderation.hitl.sink import ReviewNotificationSink, get_review_notification_sink
from app.moderation.models import ModerationAction, ModerationDecision

logger = get_logger("app.moderation.hitl.service")


class HumanReviewService:
    """
    Manages the lifecycle of Human-in-the-Loop review tickets.
    Ensures safe, atomic state transitions and strictly prevents
    destructive side effects upon ticket TTL expiration.
    """

    def __init__(
        self,
        session: AsyncSession,
        sink: ReviewNotificationSink | None = None,
        action_service: YouTubeModerationActionService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repo = ReviewRepository(session)
        self.feedback_repo = ModerationFeedbackRepository(session)
        self.sink = sink or get_review_notification_sink()
        self.action_service = action_service or get_action_service()
        self.settings = settings or get_settings()

    async def create_review(
        self,
        creator_id: str,
        stream_session_id: str,
        message_id: str,
        author_channel_id: str,
        author_display_name: str,
        message_text: str,
        confidence: int,
        severity: int,
        recommended_action: str,
        reason_code: str,
        reason: str,
        language: str = "en",
        context_summary: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> ModerationReview:
        """Create a new HITL review ticket and notify human reviewers."""
        ttl = ttl_seconds or self.settings.HITL_REVIEW_TTL_SECONDS
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl)

        review = ModerationReview(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            message_id=message_id,
            author_channel_id=author_channel_id,
            author_display_name=author_display_name,
            message_text=message_text,
            status="PENDING",
            risk_score=(confidence + severity) // 2,
            confidence=confidence,
            severity=severity,
            recommended_action=recommended_action,
            reason_code=reason_code,
            reason=reason,
            language=language,
            context_summary=context_summary or {},
            expires_at=expires_at,
        )

        self.session.add(review)
        await self.session.flush()

        # Notify sink (Discord / dashboard)
        await self.sink.notify_review_created(review, ttl_seconds=ttl)
        logger.info(
            f"Queued HITL review {review.id} for message '{message_id}' (expires in {ttl}s)"
        )
        return review

    async def approve_review(
        self,
        review_id_prefix: str,
        moderator_id: str,
        override_action: str | None = None,
        notes: str | None = None,
    ) -> tuple[bool, str]:
        """
        Approve pending review and execute the designated moderation action.
        Supports review ID prefix match (e.g. first 8 characters).
        """
        review = await self._find_review_by_prefix(review_id_prefix)
        if not review:
            return False, "REVIEW_NOT_FOUND"

        if review.status != "PENDING":
            return False, f"REVIEW_ALREADY_RESOLVED:{review.status}"

        if review.is_expired():
            # Mark expired and disallow destructive action
            await self.repo.resolve_review(
                review.id, "EXPIRED", resolved_by="SYSTEM_TTL_EXPIRATION"
            )
            return False, "REVIEW_EXPIRED_NO_ACTION"

        final_action = override_action or review.recommended_action
        await self.repo.resolve_review(
            review.id,
            status="APPROVED",
            final_action=final_action,
            resolved_by=moderator_id,
        )

        # Record moderator feedback
        await self.feedback_repo.record_feedback(
            review_id=review.id,
            creator_id=review.creator_id,
            moderator_id=moderator_id,
            decision="YES",
            action_taken=final_action,
            notes=notes,
        )

        # Execute moderation action via application-controlled service
        action_enum = getattr(ModerationAction, final_action.upper(), ModerationAction.WARN)
        decision = ModerationDecision(
            action=action_enum,
            confidence_score=1.0,
            reason=f"Human moderator approved ({review.reason})",
            requires_human_review=False,
        )

        await self.action_service.execute_decision(
            creator_id=review.creator_id,
            stream_session_id=review.stream_session_id,
            live_chat_id="",
            message_id=review.message_id,
            author_channel_id=review.author_channel_id,
            decision=decision,
        )

        logger.info(
            f"Moderator {moderator_id} APPROVED review {review.id} (Action: {final_action})"
        )
        return True, f"APPROVED:{final_action}"

    async def deny_review(
        self,
        review_id_prefix: str,
        moderator_id: str,
        notes: str | None = None,
    ) -> tuple[bool, str]:
        """
        Deny pending review: message remains in chat, no punishment executed.
        """
        review = await self._find_review_by_prefix(review_id_prefix)
        if not review:
            return False, "REVIEW_NOT_FOUND"

        if review.status != "PENDING":
            return False, f"REVIEW_ALREADY_RESOLVED:{review.status}"

        await self.repo.resolve_review(
            review.id,
            status="DENIED",
            final_action="ALLOW",
            resolved_by=moderator_id,
        )

        # Record moderator feedback
        await self.feedback_repo.record_feedback(
            review_id=review.id,
            creator_id=review.creator_id,
            moderator_id=moderator_id,
            decision="NO",
            action_taken="ALLOW",
            notes=notes,
        )

        logger.info(f"Moderator {moderator_id} DENIED review {review.id} (Allowed)")
        return True, "DENIED:ALLOW"

    async def get_pending_reviews(self, creator_id: str) -> Sequence[ModerationReview]:
        """Fetch pending reviews for creator."""
        return await self.repo.list_pending_by_creator(creator_id)

    async def _find_review_by_prefix(self, prefix: str) -> ModerationReview | None:
        """Find review matching full UUID or prefix."""
        clean_prefix = prefix.strip().lower()
        if len(clean_prefix) == 36:
            return await self.repo.get_by_id(clean_prefix)

        # Search pending reviews
        reviews = await self.repo.list_all(limit=100)
        for r in reviews:
            if r.id.lower().startswith(clean_prefix):
                return r
        return None

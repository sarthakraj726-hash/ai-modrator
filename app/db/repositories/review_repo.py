"""Repository for ModerationReview records."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.moderation_review import ModerationReview
from app.db.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[ModerationReview]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ModerationReview, session)

    async def get_by_message_id(self, message_id: str) -> ModerationReview | None:
        """Fetch review item by YouTube message ID."""
        result = await self.session.execute(
            select(ModerationReview).where(ModerationReview.message_id == message_id)
        )
        return result.scalars().first()

    async def list_pending_by_creator(
        self, creator_id: str, limit: int = 50
    ) -> Sequence[ModerationReview]:
        """List active pending review items for a creator that have not expired."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(ModerationReview)
            .where(
                ModerationReview.creator_id == creator_id,
                ModerationReview.status == "PENDING",
                ModerationReview.expires_at > now,
            )
            .order_by(ModerationReview.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def list_pending_by_session(
        self, stream_session_id: str, limit: int = 50
    ) -> Sequence[ModerationReview]:
        """List active pending review items for a specific stream session."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(ModerationReview)
            .where(
                ModerationReview.stream_session_id == stream_session_id,
                ModerationReview.status == "PENDING",
                ModerationReview.expires_at > now,
            )
            .order_by(ModerationReview.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def resolve_review(
        self,
        review_id: str,
        status: str,
        final_action: str | None = None,
        resolved_by: str | None = None,
    ) -> ModerationReview | None:
        """
        Atomically transition review status from PENDING to APPROVED, DENIED, or EXPIRED.
        """
        review = await self.get_by_id(review_id)
        if not review:
            return None

        # Guard against double resolution
        if review.status != "PENDING":
            return review

        review.status = status
        review.final_action = final_action or review.recommended_action
        review.resolved_at = datetime.now(UTC)
        review.resolved_by = resolved_by
        await self.session.flush()
        return review

    async def expire_stale_reviews(self) -> int:
        """Mark all past-due pending reviews as EXPIRED."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(ModerationReview).where(
                ModerationReview.status == "PENDING",
                ModerationReview.expires_at <= now,
            )
        )
        stale_reviews = result.scalars().all()
        count = 0
        for r in stale_reviews:
            r.status = "EXPIRED"
            r.resolved_at = now
            r.resolved_by = "SYSTEM_TTL_EXPIRATION"
            count += 1
        if count > 0:
            await self.session.flush()
        return count

"""Repository for ModerationFeedback records."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.moderation_feedback import ModerationFeedback
from app.db.repositories.base import BaseRepository


class ModerationFeedbackRepository(BaseRepository[ModerationFeedback]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ModerationFeedback, session)

    async def record_feedback(
        self,
        review_id: str,
        creator_id: str,
        moderator_id: str,
        decision: str,
        action_taken: str | None = None,
        notes: str | None = None,
    ) -> ModerationFeedback:
        """Persist moderator feedback for a review item."""
        feedback = ModerationFeedback(
            review_id=review_id,
            creator_id=creator_id,
            moderator_id=moderator_id,
            decision=decision,
            action_taken=action_taken,
            notes=notes,
        )
        self.session.add(feedback)
        await self.session.flush()
        return feedback

    async def list_by_creator(
        self, creator_id: str, limit: int = 100
    ) -> Sequence[ModerationFeedback]:
        """Fetch historical feedback decisions for a creator."""
        result = await self.session.execute(
            select(ModerationFeedback)
            .where(ModerationFeedback.creator_id == creator_id)
            .order_by(ModerationFeedback.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

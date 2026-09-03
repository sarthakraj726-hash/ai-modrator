"""Moderation feedback analytics store for evaluation benchmarks."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.moderation_feedback import ModerationFeedback
from app.db.repositories.feedback_repo import ModerationFeedbackRepository


class ModerationFeedbackStore:
    """
    Interface for tracking and aggregating human review decisions
    to power offline model evaluation and accuracy benchmarking.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ModerationFeedbackRepository(session)

    async def get_feedback_summary(self, creator_id: str) -> dict[str, Any]:
        """Aggregate moderator acceptance vs denial counts."""
        records: Sequence[ModerationFeedback] = await self.repo.list_by_creator(
            creator_id, limit=500
        )
        total = len(records)
        yes_count = sum(1 for r in records if r.decision == "YES")
        no_count = sum(1 for r in records if r.decision == "NO")
        overrule_count = sum(1 for r in records if r.decision == "OVERRULE")

        agreement_rate = (yes_count / total * 100.0) if total > 0 else 100.0

        return {
            "total_reviews_resolved": total,
            "approved_count": yes_count,
            "denied_count": no_count,
            "overrule_count": overrule_count,
            "moderator_agreement_rate_pct": round(agreement_rate, 2),
        }

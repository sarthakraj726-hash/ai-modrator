"""Viewer trust and reputation service (Layer 4 modifier)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.trust_repo import ViewerTrustRepository
from app.moderation.models import ModerationAction, ModerationDecision, ModerationLayer


class TrustService:
    """
    Manages creator-scoped viewer trust scores (0-100).
    Applies trust as a contextual tolerance modifier:
    - High trust (>80): gives benefit of the doubt for ambiguous banter, downgrading timeouts to warnings.
    - Low trust (<30): stricter thresholds for repeat offenders.
    - Extreme violations (Layer 5 ban) bypass trust modifiers completely.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ViewerTrustRepository(session)

    async def get_trust_score(
        self, creator_id: str, viewer_channel_id: str, display_name: str
    ) -> int:
        """Fetch current trust score for viewer in creator's channel."""
        profile = await self.repo.get_or_create(creator_id, viewer_channel_id, display_name)
        return profile.trust_score

    async def record_positive_interaction(
        self, creator_id: str, viewer_channel_id: str, display_name: str
    ) -> None:
        """Increment trust for regular participation."""
        await self.repo.record_interaction(
            creator_id, viewer_channel_id, display_name, positive_delta=1
        )

    async def record_violation(
        self,
        creator_id: str,
        viewer_channel_id: str,
        display_name: str,
        action: ModerationAction,
    ) -> None:
        """Penalize trust score following an authorized moderation action."""
        penalty = 10
        if action == ModerationAction.TIMEOUT:
            penalty = 25
        elif action == ModerationAction.BAN:
            penalty = 50
        await self.repo.record_violation(
            creator_id, viewer_channel_id, display_name, action.value, penalty=penalty
        )

    def apply_trust_modifier(
        self, decision: ModerationDecision, trust_score: int
    ) -> ModerationDecision:
        """
        Adjust moderation decision based on viewer's historical trust score.
        High trust viewers get warning reminders rather than immediate timeouts for mild infractions.
        """
        # Invariant: Extreme violations (BAN) can never be overridden by trust
        if (
            decision.action == ModerationAction.BAN
            or decision.layer == ModerationLayer.LAYER_5_HIDE_BAN
        ):
            return decision

        # For high-trust community members (>75), soften borderline actions
        if trust_score >= 75:
            if decision.action == ModerationAction.TIMEOUT and decision.confidence_score < 0.95:
                # Downgrade first-time timeout to warning & delete
                return ModerationDecision(
                    action=ModerationAction.DELETE,
                    layer=ModerationLayer.LAYER_2_WARNING_AND_DELETE,
                    confidence_score=decision.confidence_score,
                    reason=f"{decision.reason} (Softened due to high community trust: {trust_score})",
                    matched_rules=[*decision.matched_rules, "HIGH_TRUST_DOWNGRADE"],
                    warning_message="Gentle reminder: please keep remarks friendly.",
                )

        # For low-trust repeat offenders (<30), upgrade warning to short timeout if repeated
        if trust_score <= 30:
            if decision.action == ModerationAction.WARN and decision.confidence_score >= 0.8:
                return ModerationDecision(
                    action=ModerationAction.TIMEOUT,
                    layer=ModerationLayer.LAYER_3_SHORT_TIMEOUT,
                    confidence_score=decision.confidence_score,
                    reason=f"{decision.reason} (Escalated due to repeat low trust: {trust_score})",
                    matched_rules=[*decision.matched_rules, "LOW_TRUST_ESCALATION"],
                    suggested_timeout_seconds=60,
                    warning_message="Repeated disruptions lead to chat timeouts.",
                )

        return decision

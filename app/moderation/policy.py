"""2D Confidence x Severity Policy Engine with 5-layer progressive hierarchy."""

from app.ai.models import ModerationAIResult
from app.moderation.models import ModerationAction, ModerationDecision, ModerationLayer


class ModerationPolicyEngine:
    """
    Translates AI classification scores and rule signals into concrete,
    progressive enforcement decisions using a 2D matrix (Confidence x Severity).
    """

    @classmethod
    def evaluate_2d_policy(
        cls,
        ai_result: ModerationAIResult,
        strictness: str = "BALANCED",
        trust_score: int = 50,
    ) -> ModerationDecision:
        """
        Evaluate 2D confidence/severity matrix:
        - Confidence < 40: ALLOW / IGNORE
        - Confidence 40 - 89: FLAG_FOR_REVIEW (Human-In-The-Loop)
        - Confidence >= 90: Auto-Policy enforcement by Severity
        """
        confidence = ai_result.confidence
        severity = ai_result.severity

        # Adjust confidence thresholds by strictness setting
        review_threshold = 40
        auto_threshold = 90

        if strictness == "RELAXED":
            auto_threshold = 95
            review_threshold = 50
        elif strictness == "STRICT":
            auto_threshold = 85
            review_threshold = 30

        # 0. Benign content check
        if ai_result.category.lower() in ("none", "", "safe") or (
            severity == 0 and ai_result.recommended_action.lower() == "allow"
        ):
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                layer=None,
                confidence_score=confidence / 100.0,
                reason="Content adheres to community standards",
                requires_human_review=False,
            )

        # 1. Low Confidence: Content is likely benign or uncertain -> Allow
        if confidence < review_threshold:
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                layer=None,
                confidence_score=confidence / 100.0,
                reason="Low violation confidence; content allowed",
                requires_human_review=False,
            )

        # 2. Borderline / Ambiguous: Queue for Human-In-The-Loop review
        if confidence < auto_threshold:
            # Map suggested layer based on severity
            suggested_layer = cls._map_severity_to_layer(severity)
            return ModerationDecision(
                action=ModerationAction.FLAG_FOR_REVIEW,
                layer=suggested_layer,
                confidence_score=confidence / 100.0,
                reason=f"Ambiguous violation ({ai_result.category}, conf:{confidence}%, sev:{severity}%); flagged for HITL",
                matched_rules=[f"AI_AMBIGUOUS:{ai_result.category}"],
                requires_human_review=True,
            )

        # 3. High Confidence (>= auto_threshold): Direct 5-Layer Progressive Enforcement
        layer = cls._map_severity_to_layer(severity)
        action = cls._map_layer_to_action(layer)

        timeout_sec = 0
        if layer == ModerationLayer.LAYER_3_SHORT_TIMEOUT:
            timeout_sec = 300
        elif layer == ModerationLayer.LAYER_4_EXTENDED_TIMEOUT:
            timeout_sec = 1800

        return ModerationDecision(
            action=action,
            layer=layer,
            confidence_score=confidence / 100.0,
            reason=f"High-confidence violation ({ai_result.category}: {ai_result.short_reason})",
            matched_rules=[f"AI_VIOLATION:{ai_result.category}"],
            requires_human_review=False,
            suggested_timeout_seconds=timeout_sec,
            warning_message=cls._get_warning_text(layer),
        )

    @classmethod
    def _map_severity_to_layer(cls, severity: int) -> ModerationLayer:
        """Map severity score (0-100) to 5-layer hierarchy."""
        if severity <= 25:
            return ModerationLayer.LAYER_1_LIGHT_WARNING
        elif severity <= 50:
            return ModerationLayer.LAYER_2_WARNING_AND_DELETE
        elif severity <= 75:
            return ModerationLayer.LAYER_3_SHORT_TIMEOUT
        elif severity <= 88:
            return ModerationLayer.LAYER_4_EXTENDED_TIMEOUT
        else:
            return ModerationLayer.LAYER_5_HIDE_BAN

    @classmethod
    def _map_layer_to_action(cls, layer: ModerationLayer) -> ModerationAction:
        """Map layer to discrete action."""
        if layer == ModerationLayer.LAYER_1_LIGHT_WARNING:
            return ModerationAction.WARN
        elif layer == ModerationLayer.LAYER_2_WARNING_AND_DELETE:
            return ModerationAction.DELETE
        elif layer in (
            ModerationLayer.LAYER_3_SHORT_TIMEOUT,
            ModerationLayer.LAYER_4_EXTENDED_TIMEOUT,
        ):
            return ModerationAction.TIMEOUT
        elif layer == ModerationLayer.LAYER_5_HIDE_BAN:
            return ModerationAction.BAN
        return ModerationAction.ALLOW

    @classmethod
    def _get_warning_text(cls, layer: ModerationLayer) -> str:
        """Produce standard policy warning text."""
        if layer == ModerationLayer.LAYER_1_LIGHT_WARNING:
            return "Notice: Please maintain respectful language in the stream chat."
        elif layer == ModerationLayer.LAYER_2_WARNING_AND_DELETE:
            return "Notice: Inappropriate message deleted. Please review community guidelines."
        elif layer == ModerationLayer.LAYER_3_SHORT_TIMEOUT:
            return "Notice: You have been placed on a short timeout for community guideline violations."
        elif layer == ModerationLayer.LAYER_4_EXTENDED_TIMEOUT:
            return "Notice: Extended timeout applied due to serious chat disruptions."
        elif layer == ModerationLayer.LAYER_5_HIDE_BAN:
            return "Notice: User permanently restricted from channel live chat."
        return ""

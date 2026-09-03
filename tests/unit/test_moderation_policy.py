"""Unit tests for 2D Confidence x Severity Policy Engine and 5-layer progressive hierarchy."""

from app.ai.models import ModerationAIResult
from app.moderation.models import ModerationAction, ModerationLayer
from app.moderation.policy import ModerationPolicyEngine


class TestModerationPolicyEngine:
    def test_low_confidence_results_in_allow(self):
        result = ModerationAIResult(
            category="harassment",
            severity=50,
            confidence=30,  # Below review threshold (40)
            recommended_action="warn",
        )
        decision = ModerationPolicyEngine.evaluate_2d_policy(result)
        assert decision.action == ModerationAction.ALLOW
        assert decision.requires_human_review is False

    def test_ambiguous_confidence_routes_to_hitl(self):
        result = ModerationAIResult(
            category="harassment",
            severity=60,
            confidence=65,  # In ambiguous range [40, 89]
            recommended_action="timeout",
        )
        decision = ModerationPolicyEngine.evaluate_2d_policy(result)
        assert decision.action == ModerationAction.FLAG_FOR_REVIEW
        assert decision.requires_human_review is True
        assert decision.layer == ModerationLayer.LAYER_3_SHORT_TIMEOUT

    def test_high_confidence_progressive_escalation(self):
        # 1. Low severity -> WARN
        r_warn = ModerationAIResult(category="spam", severity=20, confidence=95)
        d_warn = ModerationPolicyEngine.evaluate_2d_policy(r_warn)
        assert d_warn.action == ModerationAction.WARN
        assert d_warn.layer == ModerationLayer.LAYER_1_LIGHT_WARNING

        # 2. Moderate severity -> DELETE
        r_del = ModerationAIResult(category="spam", severity=40, confidence=95)
        d_del = ModerationPolicyEngine.evaluate_2d_policy(r_del)
        assert d_del.action == ModerationAction.DELETE
        assert d_del.layer == ModerationLayer.LAYER_2_WARNING_AND_DELETE

        # 3. High severity -> TIMEOUT
        r_time = ModerationAIResult(category="harassment", severity=70, confidence=95)
        d_time = ModerationPolicyEngine.evaluate_2d_policy(r_time)
        assert d_time.action == ModerationAction.TIMEOUT
        assert d_time.layer == ModerationLayer.LAYER_3_SHORT_TIMEOUT
        assert d_time.suggested_timeout_seconds == 300

        # 4. Extreme severity -> BAN
        r_ban = ModerationAIResult(category="threat", severity=95, confidence=98)
        d_ban = ModerationPolicyEngine.evaluate_2d_policy(r_ban)
        assert d_ban.action == ModerationAction.BAN
        assert d_ban.layer == ModerationLayer.LAYER_5_HIDE_BAN

    def test_strictness_modifiers(self):
        result = ModerationAIResult(category="harassment", severity=50, confidence=88)

        # In BALANCED mode, 88 is ambiguous -> HITL
        d_balanced = ModerationPolicyEngine.evaluate_2d_policy(result, strictness="BALANCED")
        assert d_balanced.action == ModerationAction.FLAG_FOR_REVIEW

        # In STRICT mode, auto_threshold is 85 -> 88 triggers auto-enforcement!
        d_strict = ModerationPolicyEngine.evaluate_2d_policy(result, strictness="STRICT")
        assert d_strict.action == ModerationAction.DELETE

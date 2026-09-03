"""Unit tests for Layer 0/1 deterministic rules and Layer 2 behavioral spam detection."""

import pytest

from app.moderation.models import ModerationAction, ModerationLayer
from app.moderation.rules import LocalRuleEngine
from app.moderation.spam import BehavioralSpamDetector


class TestLocalRuleEngine:
    def test_extreme_threat_rule(self):
        decision = LocalRuleEngine.evaluate_deterministic_rules(
            "i will kill you mar dalunga doxx you"
        )
        assert decision is not None
        assert decision.action == ModerationAction.BAN
        assert decision.layer == ModerationLayer.LAYER_5_HIDE_BAN

    def test_scam_link_rule(self):
        decision = LocalRuleEngine.evaluate_deterministic_rules(
            "Join my t.me/free_crypto for money"
        )
        assert decision is not None
        assert decision.action == ModerationAction.DELETE
        assert decision.layer == ModerationLayer.LAYER_2_WARNING_AND_DELETE

    def test_severe_slur_rule(self):
        decision = LocalRuleEngine.evaluate_deterministic_rules("teri ma ki chut madarchod")
        assert decision is not None
        assert decision.action == ModerationAction.TIMEOUT
        assert decision.layer == ModerationLayer.LAYER_3_SHORT_TIMEOUT

    def test_creator_custom_rule(self):
        custom_rules = [
            {"name": "No Spoilers", "pattern": r"\b(boss dies|ending is)\b", "action": "DELETE"}
        ]
        decision = LocalRuleEngine.evaluate_deterministic_rules(
            "hey the boss dies at the end", creator_custom_rules=custom_rules
        )
        assert decision is not None
        assert decision.action == ModerationAction.DELETE

    def test_fast_allow_for_playful_banter(self):
        decision = LocalRuleEngine.evaluate_deterministic_rules("bhai ye banda pagal hai 😂")
        assert decision is not None
        assert decision.action == ModerationAction.ALLOW


@pytest.mark.asyncio
class TestBehavioralSpamDetector:
    async def test_excessive_caps_spam(self):
        detector = BehavioralSpamDetector()
        decision = await detector.evaluate_spam_signals(
            creator_id="c1",
            stream_session_id="s1",
            user_id="u1",
            text="PLEASE PLAY MINECRAFT NOW STREAMER PLEASE",
        )
        assert decision is not None
        assert decision.action == ModerationAction.WARN
        assert decision.matched_rules == ["EXCESSIVE_CAPS"]

    async def test_emoji_flood_spam(self):
        detector = BehavioralSpamDetector()
        decision = await detector.evaluate_spam_signals(
            creator_id="c1",
            stream_session_id="s1",
            user_id="u2",
            text="🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥",
        )
        assert decision is not None
        assert decision.action == ModerationAction.WARN
        assert decision.matched_rules == ["EMOJI_FLOOD"]

    async def test_rapid_burst_and_duplicate_flood(self):
        detector = BehavioralSpamDetector()
        # Send 4 identical messages quickly
        for _ in range(4):
            decision = await detector.evaluate_spam_signals(
                creator_id="c1", stream_session_id="s1", user_id="u3", text="sub to my channel"
            )
        assert decision is not None
        assert decision.action == ModerationAction.DELETE

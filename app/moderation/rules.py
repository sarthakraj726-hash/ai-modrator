"""Deterministic local moderation rules (Layer 0 and Layer 1)."""

import re
from typing import Any

from app.moderation.models import ModerationAction, ModerationDecision, ModerationLayer
from app.moderation.nlp.normalizer import MultilingualNormalizer
from app.moderation.nlp.slang import SlangNormalizer


class LocalRuleEngine:
    """
    Evaluates deterministic patterns (Layer 0 format checks & Layer 1 known violations)
    before invoking expensive LLM calls.
    """

    # Suspicious link patterns (Telegram, WhatsApp invites, free crypto/robux/nitro scams)
    SCAM_LINK_REGEX = re.compile(
        r"(t\.me/|telegram\.me/|wa\.me/|chat\.whatsapp\.com/|discord\.gg/|"
        r"free[-_]?(crypto|nitro|robux|skin|coins|follower)|claim[-_]?reward|bit\.ly/|"
        r"tinyurl\.com/|goo\.gl/|grabify|iplogger)",
        re.IGNORECASE,
    )

    # Obvious general URL regex
    URL_REGEX = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)

    # Extreme threat keywords
    EXTREME_THREAT_REGEX = re.compile(
        r"\b(i will kill you|mar dalunga|bomb lagauga|doxx you|home address)\b",
        re.IGNORECASE,
    )

    @classmethod
    def evaluate_deterministic_rules(
        cls,
        text: str,
        creator_custom_rules: list[dict[str, Any]] | None = None,
    ) -> ModerationDecision | None:
        """
        Evaluate deterministic rules.
        Returns ModerationDecision if a definite rule matched, or None if evaluation should continue to AI.
        """
        if not text or not text.strip():
            return ModerationDecision(action=ModerationAction.ALLOW, reason="Empty text")

        normalized = MultilingualNormalizer.normalize_text(text)
        deobfuscated = MultilingualNormalizer.deobfuscate_leet(normalized)

        # 1. Extreme Threats (Immediate High Severity Layer 5)
        if cls.EXTREME_THREAT_REGEX.search(normalized) or cls.EXTREME_THREAT_REGEX.search(
            deobfuscated
        ):
            return ModerationDecision(
                action=ModerationAction.BAN,
                layer=ModerationLayer.LAYER_5_HIDE_BAN,
                confidence_score=1.0,
                reason="Severe threat or violent solicitation detected",
                matched_rules=["EXTREME_VIOLENT_THREAT"],
                requires_human_review=False,
            )

        # 2. Known Malicious Scam Links / External Invites
        if cls.SCAM_LINK_REGEX.search(text) or cls.SCAM_LINK_REGEX.search(deobfuscated):
            return ModerationDecision(
                action=ModerationAction.DELETE,
                layer=ModerationLayer.LAYER_2_WARNING_AND_DELETE,
                confidence_score=1.0,
                reason="Unauthorized scam link or private invite detected",
                matched_rules=["SCAM_INVITE_LINK"],
                warning_message="External invite and promotion links are not permitted in chat.",
            )

        # 3. Severe Hate / Profanity Slurs
        if SlangNormalizer.has_severe_slur(normalized) or SlangNormalizer.has_severe_slur(
            deobfuscated
        ):
            return ModerationDecision(
                action=ModerationAction.TIMEOUT,
                layer=ModerationLayer.LAYER_3_SHORT_TIMEOUT,
                confidence_score=0.95,
                reason="Severe profanity or hate slur detected",
                matched_rules=["SEVERE_HATE_PROFANITY"],
                suggested_timeout_seconds=300,
                warning_message="Please keep the chat respectful and civil.",
            )

        # 4. Creator Custom Deterministic Blocklist Rules
        if creator_custom_rules:
            for r in creator_custom_rules:
                pat = r.get("pattern")
                if pat and re.search(pat, normalized, re.IGNORECASE):
                    act_name = r.get("action", "WARN").upper()
                    action = getattr(ModerationAction, act_name, ModerationAction.WARN)
                    return ModerationDecision(
                        action=action,
                        layer=ModerationLayer.LAYER_2_WARNING_AND_DELETE,
                        confidence_score=1.0,
                        reason=f"Matched custom creator rule: {r.get('name', 'Custom Blocklist')}",
                        matched_rules=[f"CUSTOM_RULE:{r.get('name', 'custom')}"],
                    )

        # 5. Fast Allow for Playful Banter
        if SlangNormalizer.is_likely_playful_banter(normalized):
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                layer=None,
                confidence_score=0.9,
                reason="Identified as playful banter or gaming hype",
                matched_rules=["PLAYFUL_BANTER_FAST_ALLOW"],
            )

        return None

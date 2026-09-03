"""Behavioral spam, flood, and repetition detector (Layer 2)."""

import re
import time

from app.cache.redis import RedisClient, get_redis_client
from app.moderation.models import ModerationAction, ModerationDecision, ModerationLayer


class BehavioralSpamDetector:
    """
    Detects rate-burst flooding, excessive character repetition,
    wall of caps, and duplicate message spam using Redis sliding windows.
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        self.redis_client = redis_client or get_redis_client()
        self._local_history: dict[str, list[tuple[str, float]]] = {}

    async def evaluate_spam_signals(
        self,
        creator_id: str,
        stream_session_id: str,
        user_id: str,
        text: str,
    ) -> ModerationDecision | None:
        """
        Evaluate behavioral spam signals. Returns ModerationDecision if spam detected, else None.
        """
        now = time.time()
        cleaned = text.strip()

        # 1. Check Excessive CAPS (>75% uppercase for texts >12 characters)
        alpha_chars = [c for c in cleaned if c.isalpha()]
        if len(alpha_chars) > 12:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio > 0.85:
                return ModerationDecision(
                    action=ModerationAction.WARN,
                    layer=ModerationLayer.LAYER_1_LIGHT_WARNING,
                    confidence_score=0.9,
                    reason="Excessive caps lock spam",
                    matched_rules=["EXCESSIVE_CAPS"],
                    warning_message="Please avoid using all-caps in chat.",
                )

        # 2. Check Emoji Flood (>10 emojis in a short message)
        emoji_count = len(re.findall(r"[\U00010000-\U0010ffff]", cleaned))
        if emoji_count > 12 and len(cleaned) < 50:
            return ModerationDecision(
                action=ModerationAction.WARN,
                layer=ModerationLayer.LAYER_1_LIGHT_WARNING,
                confidence_score=0.85,
                reason="Emoji flood spam",
                matched_rules=["EMOJI_FLOOD"],
                warning_message="Please avoid emoji spamming.",
            )

        # 3. Check Duplicate Message Repetition & Rapid Bursts
        cache_key = f"spam:user:{creator_id}:{stream_session_id}:{user_id}"
        recent_entries = self._local_history.setdefault(cache_key, [])

        # Prune entries older than 20 seconds
        recent_entries[:] = [e for e in recent_entries if now - e[1] < 20.0]
        recent_entries.append((cleaned.lower(), now))

        # Check rapid burst (>6 messages in 5 seconds)
        last_5s_count = sum(1 for e in recent_entries if now - e[1] < 5.0)
        if last_5s_count >= 6:
            return ModerationDecision(
                action=ModerationAction.DELETE,
                layer=ModerationLayer.LAYER_2_WARNING_AND_DELETE,
                confidence_score=0.95,
                reason="Rapid chat message flooding",
                matched_rules=["BURST_FLOOD"],
                warning_message="Slow down! Please do not flood the chat.",
            )

        # Check identical duplicate messages (>3 in 15 seconds)
        duplicate_count = sum(1 for e in recent_entries if e[0] == cleaned.lower())
        if duplicate_count >= 4:
            return ModerationDecision(
                action=ModerationAction.DELETE,
                layer=ModerationLayer.LAYER_2_WARNING_AND_DELETE,
                confidence_score=0.95,
                reason="Repeated copy-paste duplicate spam",
                matched_rules=["DUPLICATE_MESSAGE_SPAM"],
                warning_message="Please avoid repeating the same message.",
            )

        return None

"""Unified 5-layer multilingual Moderation Engine implementation."""

from typing import Any

from app.ai.budget import AIBudgetManager, get_ai_budget_manager
from app.ai.coalescer import AIRequestCoalescer, get_ai_coalescer
from app.ai.models import (
    ChatMessage,
    ChatRole,
    ModelTier,
    ModerationAIResult,
)
from app.ai.openrouter import get_ai_provider
from app.ai.provider import AIProvider
from app.core.logging import get_logger
from app.moderation.interface import ModerationEngine
from app.moderation.models import (
    ModerationAction,
    ModerationDecision,
    ReviewItem,
)
from app.moderation.nlp.language import LanguageDetector
from app.moderation.nlp.normalizer import MultilingualNormalizer
from app.moderation.nlp.slang import SlangNormalizer
from app.moderation.policy import ModerationPolicyEngine
from app.moderation.rules import LocalRuleEngine
from app.moderation.spam import BehavioralSpamDetector
from app.youtube.models import YouTubeChatMessage

logger = get_logger("app.moderation.engine")


class HonneyModerationEngine(ModerationEngine):
    """
    Five-layer progressive, multilingual moderation pipeline.
    Combines local-first fast path with LLM semantic reasoning and 2D policy matrix.
    """

    def __init__(
        self,
        ai_provider: AIProvider | None = None,
        spam_detector: BehavioralSpamDetector | None = None,
        ai_budget: AIBudgetManager | None = None,
        coalescer: AIRequestCoalescer | None = None,
    ) -> None:
        self.ai_provider = ai_provider or get_ai_provider()
        self.spam_detector = spam_detector or BehavioralSpamDetector()
        self.ai_budget = ai_budget or get_ai_budget_manager()
        self.coalescer = coalescer or get_ai_coalescer()
        self._pending_reviews: dict[str, list[ReviewItem]] = {}

    async def evaluate_message(
        self,
        creator_id: str,
        message: YouTubeChatMessage,
        user_history: dict[str, Any] | None = None,
    ) -> ModerationDecision:
        """
        Execute full 5-layer moderation pipeline:
        1. Normalization & Language Detection
        2. Layer 0 & 1: Deterministic Rules & Scams
        3. Layer 2: Behavioral Spam & Flood
        4. Layer 3: AI Semantic Understanding (if ambiguous/needed)
        5. Layer 4: Trust Score Adjustment
        6. Layer 5: Policy 2D Matrix (Confidence x Severity)
        """
        text = message.display_message
        author_id = message.author.channel_id
        author_name = message.author.display_name
        stream_session_id = getattr(message, "stream_session_id", "default-stream")

        # Exclude stream owner / verified channel moderators from automated bans
        if message.author.is_chat_owner or message.author.is_chat_moderator:
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                reason="Author is owner or moderator",
                confidence_score=1.0,
            )

        # 1. Normalization
        normalized = MultilingualNormalizer.normalize_text(text)
        language = LanguageDetector.detect_language(normalized)

        # 2. Layer 0 & 1: Deterministic Rules
        local_decision = LocalRuleEngine.evaluate_deterministic_rules(normalized)
        if local_decision is not None:
            return local_decision

        # 3. Layer 2: Behavioral Spam Detection
        spam_decision = await self.spam_detector.evaluate_spam_signals(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            user_id=author_id,
            text=text,
        )
        if spam_decision is not None:
            return spam_decision

        # 4. Check if message is obviously safe short chat (e.g. 'hello', 'lol', 'nice game')
        if len(normalized.split()) <= 3 and not SlangNormalizer.has_severe_slur(normalized):
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                reason="Safe short chat message",
                confidence_score=0.99,
            )

        # 5. Layer 3: AI Semantic Classification Gate
        can_dispatch, budget_reason = await self.ai_budget.can_dispatch(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            user_id=author_id,
            task_type="moderation_classify",
        )

        if not can_dispatch:
            logger.warning(
                f"Skipping AI moderation due to budget gate ({budget_reason}). Falling back to ALLOW."
            )
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                reason=f"AI classification rate-limited ({budget_reason})",
                confidence_score=0.5,
            )

        # Build single-flight coalescing key
        coalesce_key = self.coalescer.make_key(
            creator_id, stream_session_id, message.message_id, "moderation_classify"
        )

        async def _call_ai() -> ModerationAIResult:
            messages = [
                ChatMessage(
                    role=ChatRole.SYSTEM,
                    content=(
                        "You are Honney's real-time live-chat moderation classifier. "
                        "Evaluate the following message for hate speech, targeted harassment, threats, or severe abuse. "
                        "Distinguish friendly gaming trash talk and playful Hinglish banter (e.g. 'tu pagal hai lol') "
                        "from genuine abuse. Output structured JSON matching the schema."
                    ),
                ),
                ChatMessage(
                    role=ChatRole.USER,
                    content=f'Speaker: @{author_name}\nLanguage: {language}\nMessage: "{normalized}"',
                ),
            ]
            return await self.ai_provider.classify(
                messages,
                response_model=ModerationAIResult,
                model_tier=ModelTier.FAST,
            )

        try:
            ai_result = await self.coalescer.execute(coalesce_key, _call_ai)
            await self.ai_budget.record_dispatch(
                creator_id, stream_session_id, user_id=author_id, tokens_used=50
            )
        except Exception as e:
            logger.error(f"AI moderation classification failed: {e}. Defaulting to safe ALLOW.")
            return ModerationDecision(
                action=ModerationAction.ALLOW,
                reason="AI classification error; safe fallback applied",
                confidence_score=0.5,
            )

        # 6. Layer 4 & 5: Evaluate 2D Policy Engine Matrix
        strictness = (user_history or {}).get("moderation_strictness", "BALANCED")
        trust_score = (user_history or {}).get("trust_score", 50)

        decision = ModerationPolicyEngine.evaluate_2d_policy(
            ai_result=ai_result,
            strictness=strictness,
            trust_score=trust_score,
        )

        return decision

    async def queue_for_human_review(self, item: ReviewItem) -> str:
        """Submit an ambiguous high-stakes decision to human moderator review queue."""
        reviews = self._pending_reviews.setdefault(item.creator_id, [])
        reviews.append(item)
        logger.info(f"Queued ReviewItem {item.item_id} for creator {item.creator_id}")
        return item.item_id

    async def get_pending_reviews(self, creator_id: str) -> list[ReviewItem]:
        """Fetch pending human-in-the-loop review items."""
        return [r for r in self._pending_reviews.get(creator_id, []) if r.status == "PENDING"]


_global_moderation_engine: ModerationEngine | None = None


def get_moderation_engine() -> ModerationEngine:
    """Return singleton ModerationEngine."""
    global _global_moderation_engine
    if _global_moderation_engine is None:
        _global_moderation_engine = HonneyModerationEngine()
    return _global_moderation_engine

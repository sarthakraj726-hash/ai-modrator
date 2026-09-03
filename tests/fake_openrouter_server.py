"""Simulated OpenRouter gateway with fault injection and structured output capabilities."""

from typing import Any

from app.ai.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    ModelTier,
    ModerationAIResult,
    TokenUsage,
)
from app.ai.provider import AIProvider


class FakeOpenRouterProvider(AIProvider):
    """
    In-memory OpenRouter mock allowing deterministic unit/integration testing
    and chaos fault injection without external network or API keys.
    """

    def __init__(self) -> None:
        self.call_count: int = 0
        self.models_called: list[str] = []
        self.injected_exception: Exception | None = None
        self.latency_seconds: float = 0.0
        self.custom_moderation_results: dict[str, ModerationAIResult] = {}

    def set_injected_exception(self, exc: Exception | None) -> None:
        self.injected_exception = exc

    def register_moderation_result(
        self, message_substring: str, result: ModerationAIResult
    ) -> None:
        self.custom_moderation_results[message_substring] = result

    def get_provider_name(self) -> str:
        return "fake-openrouter"

    async def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        model = request.model or "fake-model"
        self.models_called.append(model)

        if self.injected_exception:
            raise self.injected_exception

        last_user_msg = ""
        for m in reversed(request.messages):
            if m.role.value == "user":
                last_user_msg = m.content
                break

        return CompletionResponse(
            content=f"Honney: Thanks for the message! (re: {last_user_msg[:30]})",
            model_used=model,
            usage=TokenUsage(prompt_tokens=20, completion_tokens=15, total_tokens=35),
            finish_reason="stop",
        )

    async def classify(
        self,
        messages: list[ChatMessage],
        response_model: type[Any],
        model_tier: ModelTier = ModelTier.FAST,
    ) -> Any:
        self.call_count += 1
        model = f"fake-{model_tier.value.lower()}"
        self.models_called.append(model)

        if self.injected_exception:
            raise self.injected_exception

        # Inspect prompt message content
        prompt_text = " ".join(m.content for m in messages).lower()

        # Check registered custom results
        for sub, res in self.custom_moderation_results.items():
            if sub.lower() in prompt_text:
                return res

        # Default classification heuristics for testing
        if response_model == ModerationAIResult:
            if "kill" in prompt_text or "mar dalunga" in prompt_text:
                return ModerationAIResult(
                    category="threat",
                    severity=95,
                    confidence=98,
                    intent="hostile",
                    recommended_action="ban",
                    reason_code="VIOLENT_THREAT",
                    short_reason="Direct violent threat",
                )
            elif "chutiya" in prompt_text or "gandu" in prompt_text or "madarchod" in prompt_text:
                return ModerationAIResult(
                    category="harassment",
                    severity=80,
                    confidence=95,
                    intent="hostile",
                    recommended_action="timeout",
                    reason_code="SEVERE_ABUSE",
                    short_reason="Hostile slur",
                )
            elif "bekar" in prompt_text or "nalla" in prompt_text:
                return ModerationAIResult(
                    category="harassment",
                    severity=45,
                    confidence=60,  # Ambiguous -> HITL
                    intent="provocative",
                    recommended_action="review",
                    reason_code="BORDERLINE_HARASSMENT",
                    short_reason="Borderline comment",
                    requires_human_review=True,
                )
            else:
                return ModerationAIResult(
                    category="none",
                    severity=0,
                    confidence=99,
                    intent="playful" if "lol" in prompt_text or "😂" in prompt_text else "neutral",
                    recommended_action="allow",
                    reason_code="NORMAL_CHAT",
                    short_reason="Safe content",
                )

        return response_model()

    async def generate_reply(
        self,
        messages: list[ChatMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 100,
    ) -> CompletionResponse:
        return await self.generate_completion(
            CompletionRequest(
                messages=messages, model=f"fake-{model_tier.value.lower()}", max_tokens=max_tokens
            )
        )

    async def summarize(self, text: str, max_words: int = 50) -> str:
        return f"Summary of chat: active and engaging ({len(text)} chars)."

    async def health_check(self) -> bool:
        return self.injected_exception is None

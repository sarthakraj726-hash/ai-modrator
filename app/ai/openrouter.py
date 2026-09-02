"""OpenRouter API provider implementation with model fallback and token accounting."""

from typing import Any

import httpx

from app.ai.models import (
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from app.ai.provider import AIProvider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.circuit_breaker import CircuitBreaker

logger = get_logger("app.ai.openrouter")


class OpenRouterProvider(AIProvider):
    """
    OpenRouter LLM gateway client supporting model fallback chains,
    circuit breaker protection, and token usage accounting.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = base_url or settings.OPENROUTER_BASE_URL
        self.default_model = default_model or settings.OPENROUTER_DEFAULT_MODEL
        self.circuit_breaker = CircuitBreaker(
            name="openrouter-api",
            failure_threshold=4,
            recovery_timeout_seconds=45.0,
        )

    def get_provider_name(self) -> str:
        return "openrouter"

    async def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Execute chat completion through OpenRouter.
        Iterates through model candidate and fallback models on failure.
        """
        models_to_try = [
            request.model or self.default_model,
            *request.fallback_models,
        ]
        # Deduplicate while preserving order
        models_to_try = list(dict.fromkeys(models_to_try))

        # In testing / mock mode without API key, return synthetic response
        if not self.api_key or self.api_key.startswith("your_") or "dev" in self.api_key:
            selected_model = models_to_try[0]
            logger.info(f"OpenRouter simulated response using model: {selected_model}")
            return CompletionResponse(
                content=f"[Simulated AI Response from {selected_model}]",
                model_used=selected_model,
                usage=TokenUsage(prompt_tokens=25, completion_tokens=15, total_tokens=40),
            )

        last_exception: Exception | None = None

        for model in models_to_try:
            try:
                return await self._call_model(model, request)
            except Exception as e:
                logger.warning(
                    f"OpenRouter model '{model}' generation failed: {e}. Trying fallback..."
                )
                last_exception = e

        raise RuntimeError(f"All OpenRouter model candidates failed. Last error: {last_exception}")

    async def _call_model(self, model: str, request: CompletionRequest) -> CompletionResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/sarthakraj726-hash/ai-modrator",
            "X-Title": "Goddess AI Modrator",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"OpenRouter error ({resp.status_code}): {resp.text}")
                return resp.json()

        data = await self.circuit_breaker.execute(_do_request)

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        raw_usage = data.get("usage", {})

        return CompletionResponse(
            content=msg.get("content", ""),
            model_used=model,
            usage=TokenUsage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                total_tokens=raw_usage.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )


_global_ai_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Return singleton AIProvider."""
    global _global_ai_provider
    if _global_ai_provider is None:
        _global_ai_provider = OpenRouterProvider()
    return _global_ai_provider

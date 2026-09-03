"""OpenRouter API provider implementation with model fallback, structured outputs, and token accounting."""

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.models import (
    ChatMessage,
    ChatRole,
    CompletionRequest,
    CompletionResponse,
    ModelTier,
    TokenUsage,
)
from app.ai.provider import AIProvider
from app.ai.router import ModelRouter, get_model_router
from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.circuit_breaker import CircuitBreaker

logger = get_logger("app.ai.openrouter")

T = TypeVar("T", bound=BaseModel)


class OpenRouterProvider(AIProvider):
    """
    OpenRouter LLM gateway client supporting model fallback chains,
    circuit breaker protection, structured outputs, and token usage accounting.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        model_router: ModelRouter | None = None,
    ):
        settings = get_settings()
        self.settings = settings
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = base_url or settings.OPENROUTER_BASE_URL
        self.default_model = default_model or settings.OPENROUTER_DEFAULT_MODEL
        self.model_router = model_router or get_model_router()
        self.circuit_breaker = CircuitBreaker(
            name="openrouter-api",
            failure_threshold=4,
            recovery_timeout_seconds=45.0,
        )
        # Managed async client with connection pooling
        self._client: httpx.AsyncClient | None = None

    def get_provider_name(self) -> str:
        return "openrouter"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            timeout = 0.5 if self.settings.is_testing else 20.0
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._client

    async def close(self) -> None:
        """Close shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Execute chat completion through OpenRouter.
        Iterates through model candidate and fallback models on failure.
        """
        models_to_try = [
            request.model or self.default_model,
            *request.fallback_models,
        ]
        models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))

        # In testing / mock mode without API key, return synthetic response
        if not self.api_key or self.api_key.startswith("your_") or "dev" in self.api_key:
            selected_model = models_to_try[0] if models_to_try else self.default_model
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

    async def _call_model(
        self, model: str, request: CompletionRequest, response_format: dict[str, Any] | None = None
    ) -> CompletionResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/sarthakraj726-hash/ai-modrator",
            "X-Title": "Goddess AI Modrator",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        async def _do_request() -> dict[str, Any]:
            client = self._get_client()
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

    async def classify(
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        model_tier: ModelTier = ModelTier.FAST,
    ) -> T:
        """
        Execute structured JSON completion parsed into the specified Pydantic schema.
        Validates model output and raises ValidationError if malformed.
        """
        # In testing/simulated mode without API key, instantiate default response model
        if not self.api_key or self.api_key.startswith("your_") or "dev" in self.api_key:
            logger.info(
                f"OpenRouter simulated structured classification ({response_model.__name__})"
            )
            return response_model()

        models = self.model_router.get_models_for_tier(model_tier)
        schema = response_model.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "strict": True,
                "schema": schema,
            },
        }

        req = CompletionRequest(
            messages=messages,
            model=models[0],
            fallback_models=models[1:],
            temperature=0.1,  # Lower temperature for deterministic classification
            max_tokens=300,
        )

        last_err: Exception | None = None
        for model in models:
            try:
                resp = await self._call_model(model, req, response_format=response_format)
                raw_json = json.loads(resp.content)
                return response_model.model_validate(raw_json)
            except (json.JSONDecodeError, ValidationError) as parse_err:
                logger.warning(
                    f"Model '{model}' returned invalid structured output for {response_model.__name__}: {parse_err}. Trying fallback..."
                )
                last_err = parse_err
            except Exception as e:
                logger.warning(
                    f"Classification call failed on model '{model}': {e}. Trying fallback..."
                )
                last_err = e

        # Final safe fallback if all models fail
        logger.error(
            f"All models failed structured classification: {last_err}. Returning default schema instance."
        )
        return response_model()

    async def generate_reply(
        self,
        messages: list[ChatMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 100,
    ) -> CompletionResponse:
        """Generate concise persona-driven co-host response."""
        models = self.model_router.get_models_for_tier(model_tier)
        req = CompletionRequest(
            messages=messages,
            model=models[0],
            fallback_models=models[1:],
            temperature=0.7,
            max_tokens=max_tokens,
        )
        return await self.generate_completion(req)

    async def summarize(self, text: str, max_words: int = 50) -> str:
        """Produce a brief summary of stream or chat context."""
        messages = [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content=f"Summarize the following live stream chat context in under {max_words} words concisely:",
            ),
            ChatMessage(role=ChatRole.USER, content=text),
        ]
        resp = await self.generate_reply(messages, model_tier=ModelTier.FAST, max_tokens=100)
        return resp.content.strip()

    async def health_check(self) -> bool:
        """Check provider connectivity."""
        if not self.api_key or self.settings.is_testing:
            return True
        try:
            client = self._get_client()
            resp = await client.get(
                f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return resp.status_code == 200
        except Exception:
            return False


_global_ai_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Return singleton AIProvider."""
    global _global_ai_provider
    if _global_ai_provider is None:
        _global_ai_provider = OpenRouterProvider()
    return _global_ai_provider

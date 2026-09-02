"""Unit tests for OpenRouter provider and AI models."""

import pytest

from app.ai.models import ChatMessage, ChatRole, CompletionRequest
from app.ai.openrouter import OpenRouterProvider


@pytest.mark.asyncio
async def test_openrouter_simulated_completion():
    provider = OpenRouterProvider(api_key="")
    assert provider.get_provider_name() == "openrouter"

    request = CompletionRequest(
        messages=[
            ChatMessage(role=ChatRole.USER, content="Hello AI"),
        ],
        model="anthropic/claude-3.5-sonnet",
    )

    response = await provider.generate_completion(request)
    assert response.content is not None
    assert response.model_used == "anthropic/claude-3.5-sonnet"
    assert response.usage.total_tokens > 0

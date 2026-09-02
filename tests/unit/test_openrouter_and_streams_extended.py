"""Extended unit tests for OpenRouter provider and stream workers."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import ChatMessage, ChatRole, CompletionRequest
from app.ai.openrouter import OpenRouterProvider
from app.services.stream_service import StreamService
from app.workers.session import StreamWorkerSession, WorkerState


@pytest.mark.asyncio
async def test_openrouter_provider_http_mocked():
    def mock_openrouter(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello human!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    provider = OpenRouterProvider(
        api_key="sk-or-v1-validkey123456789012345678901234567890123456789012345678901234"
    )

    # Mock _call_model using MockTransport
    async def mocked_call_model(model, req):
        transport = httpx.MockTransport(mock_openrouter)
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", json={})
            data = resp.json()
            choice = data["choices"][0]["message"]["content"]
            from app.ai.models import CompletionResponse, TokenUsage

            return CompletionResponse(
                content=choice,
                model_used=model,
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )

    provider._call_model = mocked_call_model

    req = CompletionRequest(
        messages=[ChatMessage(role=ChatRole.USER, content="Hi")],
        model="anthropic/claude-3.5-sonnet",
        fallback_models=["openai/gpt-4o"],
    )
    res = await provider.generate_completion(req)
    assert res.content == "Hello human!"
    assert res.usage.total_tokens == 15


@pytest.mark.asyncio
async def test_stream_service_not_found(db_session: AsyncSession):
    from app.core.exceptions import EntityNotFoundError

    s_service = StreamService(db_session)
    with pytest.raises(EntityNotFoundError):
        await s_service.get_stream("non-existent-session")

    with pytest.raises(EntityNotFoundError):
        await s_service.disconnect_stream("non-existent-session")


@pytest.mark.asyncio
async def test_stream_worker_session_methods():
    session = StreamWorkerSession(
        session_id="test-sess-diag",
        creator_id="test-c",
        video_id="test-v",
    )
    status = session.get_status()
    assert status["session_id"] == "test-sess-diag"
    assert status["state"] == WorkerState.IDLE.value
    assert status["messages_processed"] == 0


def test_console_logger_formatter():
    import logging

    from app.core.logging import ConsoleLogFormatter

    formatter = ConsoleLogFormatter()
    record = logging.LogRecord(
        name="test.console",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Human message",
        args=(),
        exc_info=None,
    )
    res = formatter.format(record)
    assert "Human message" in res


@pytest.mark.asyncio
async def test_redis_ttl_and_expire():
    from app.cache.redis import InMemoryRedisFallback

    fallback = InMemoryRedisFallback()
    await fallback.set("test_key", "val", ex=10)
    assert await fallback.ttl("test_key") <= 10
    assert await fallback.ttl("missing_key") == -2

    await fallback.expire("test_key", 20)
    assert await fallback.ttl("test_key") > 10
    await fallback.close()

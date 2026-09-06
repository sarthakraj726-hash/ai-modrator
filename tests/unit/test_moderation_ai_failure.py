"""Safety regression tests for AI moderation failure handling."""

import pytest

from app.moderation.engine import HonneyModerationEngine
from app.moderation.models import ModerationAction
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage


class FailingAIProvider:
    async def classify(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("simulated provider outage")


@pytest.mark.asyncio
async def test_ai_classification_failure_requires_human_review() -> None:
    """Ambiguous content must not become an automatic allow on provider failure."""
    engine = HonneyModerationEngine(ai_provider=FailingAIProvider())
    message = YouTubeChatMessage(
        message_id="provider-failure-1",
        live_chat_id="chat-1",
        stream_session_id="stream-1",
        author=YouTubeAuthor(channel_id="viewer-1", display_name="Viewer"),
        display_message="I think your gameplay is suspicious and you should answer for it",
    )

    decision = await engine.evaluate_message("creator-1", message)

    assert decision.action is ModerationAction.FLAG_FOR_REVIEW
    assert decision.requires_human_review is True
    assert "unavailable" in decision.reason.lower()

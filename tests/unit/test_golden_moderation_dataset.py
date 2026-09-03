"""Golden moderation evaluation test runner iterating through test fixtures."""

import json
from pathlib import Path

import pytest

from app.moderation.engine import HonneyModerationEngine
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage
from tests.fake_openrouter_server import FakeOpenRouterProvider


@pytest.mark.asyncio
async def test_golden_moderation_dataset_benchmark():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "moderation" / "golden_dataset.json"
    with open(fixture_path, encoding="utf-8") as f:
        fixtures = json.load(f)

    fake_ai = FakeOpenRouterProvider()
    engine = HonneyModerationEngine(ai_provider=fake_ai)

    passed_count = 0
    total_count = len(fixtures)

    for item in fixtures:
        msg_id = item["id"]
        text = item["text"]
        expected_action = item["expected_action"]

        msg = YouTubeChatMessage(
            message_id=msg_id,
            live_chat_id="chat-bench",
            author=YouTubeAuthor(channel_id=f"author-{msg_id}", display_name=f"User_{msg_id}"),
            display_message=text,
        )
        msg.stream_session_id = "session-bench"

        decision = await engine.evaluate_message(creator_id="creator-bench", message=msg)

        assert decision.action.value == expected_action, (
            f"Fixture {msg_id} failed: '{text}' -> expected {expected_action}, got {decision.action.value} ({decision.reason})"
        )
        passed_count += 1

    assert passed_count == total_count

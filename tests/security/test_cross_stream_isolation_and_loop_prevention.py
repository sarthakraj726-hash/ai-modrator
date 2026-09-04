"""Tests for Honney co-host self-trigger loop prevention and cross-stream isolation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.events.schemas import ChatMessageReceivedEvent
from app.persona.triggers import ResponseTriggerEngine, StreamContextEngine, TriggerType
from app.workers.intelligence import StreamIntelligenceCoordinator


def test_honney_self_trigger_loop_prevention_in_trigger_engine():
    """Verify that messages from Honney or bots never produce a co-host response trigger."""
    context = StreamContextEngine()

    # 1. Message from Honney containing greetings and questions
    trigger_type, kw = ResponseTriggerEngine.evaluate_trigger(
        text="Hey chat, how are you all doing today? @honney",
        stream_session_id="stream-sess-1",
        context_engine=context,
        author_name="Honney",
        is_bot=False,
    )
    assert trigger_type == TriggerType.NONE
    assert kw == ""

    # 2. Message with is_bot=True
    trigger_type2, kw2 = ResponseTriggerEngine.evaluate_trigger(
        text="Hello world!",
        stream_session_id="stream-sess-1",
        context_engine=context,
        author_name="random_user",
        is_bot=True,
    )
    assert trigger_type2 == TriggerType.NONE

    # 3. Normal viewer asking question triggers normally
    trigger_type3, kw3 = ResponseTriggerEngine.evaluate_trigger(
        text="What game is this?",
        stream_session_id="stream-sess-1",
        context_engine=context,
        author_name="real_viewer_123",
        is_bot=False,
    )
    assert trigger_type3 == TriggerType.QUESTION


@pytest.mark.asyncio
async def test_coordinator_drops_bot_and_honney_messages():
    """Verify StreamIntelligenceCoordinator drops self/bot messages to prevent recursive loops."""
    coordinator = StreamIntelligenceCoordinator()
    coordinator.moderation_engine = MagicMock()
    coordinator.moderation_engine.evaluate_message = AsyncMock()

    # Event simulating Honney posting a message back to chat
    self_event = ChatMessageReceivedEvent(
        creator_id="c-1",
        stream_session_id="stream-sess-1",
        message_id="msg-self-1",
        author_channel_id="HONNEY_BOT",
        author_display_name="Honney",
        message_text="Hello viewers! Welcome to the stream.",
        is_bot=True,
    )

    await coordinator._handle_chat_message(self_event)

    # Moderation and Co-host should never be invoked for Honney's own message
    assert coordinator.moderation_engine.evaluate_message.call_count == 0
    assert "stream-sess-1" not in coordinator._recent_chat_history


@pytest.mark.asyncio
async def test_cross_stream_chat_context_isolation():
    """Verify that concurrent streams maintain strictly isolated sliding chat contexts."""
    coordinator = StreamIntelligenceCoordinator()
    coordinator.session_factory = False
    coordinator.game_engine = MagicMock()
    coordinator.game_engine.evaluate_chat_guess = AsyncMock(return_value=(False, None))
    coordinator.xp_manager = MagicMock()
    coordinator.xp_manager.process_chat_message = AsyncMock()
    coordinator.moderation_engine = MagicMock()
    decision_mock = MagicMock()
    decision_mock.action.value = "ALLOW"
    decision_mock.requires_human_review = False
    coordinator.moderation_engine.evaluate_message = AsyncMock(return_value=decision_mock)

    # Stream A messages
    event_a = ChatMessageReceivedEvent(
        creator_id="creator-A",
        stream_session_id="stream-session-AAA",
        message_id="msg-a1",
        author_channel_id="viewer-1",
        author_display_name="Alice",
        message_text="Hello from Stream A!",
    )

    # Stream B messages
    event_b = ChatMessageReceivedEvent(
        creator_id="creator-B",
        stream_session_id="stream-session-BBB",
        message_id="msg-b1",
        author_channel_id="viewer-2",
        author_display_name="Bob",
        message_text="Different topic on Stream B!",
    )

    await coordinator._handle_chat_message(event_a)
    await coordinator._handle_chat_message(event_b)

    history_a = coordinator._recent_chat_history.get("stream-session-AAA", [])
    history_b = coordinator._recent_chat_history.get("stream-session-BBB", [])

    assert len(history_a) == 1
    assert "Alice: Hello from Stream A!" in history_a[0]
    assert len(history_b) == 1
    assert "Bob: Different topic on Stream B!" in history_b[0]

    # Verify zero cross-talk between stream histories
    assert not any("Stream B" in line for line in history_a)
    assert not any("Stream A" in line for line in history_b)

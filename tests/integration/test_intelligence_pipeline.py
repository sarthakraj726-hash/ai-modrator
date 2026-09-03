"""Integration tests for the full stream intelligence pipeline."""

import asyncio

import pytest

from app.ai.budget import AIBudgetManager
from app.events.bus import EventBus
from app.events.schemas import ChatMessageReceivedEvent
from app.moderation.actions import YouTubeModerationActionService
from app.moderation.engine import HonneyModerationEngine
from app.persona.engine import HonneyPersonaEngine
from app.persona.models import PersonaProfile, PersonaType
from app.workers.intelligence import StreamIntelligenceCoordinator
from tests.fake_openrouter_server import FakeOpenRouterProvider


class MockActionService(YouTubeModerationActionService):
    def __init__(self):
        super().__init__()
        self.executed_decisions = []

    async def execute_decision(
        self, creator_id, stream_session_id, live_chat_id, message_id, author_channel_id, decision
    ):
        self.executed_decisions.append(
            {
                "creator_id": creator_id,
                "message_id": message_id,
                "action": decision.action.value,
                "reason": decision.reason,
            }
        )
        return True


@pytest.mark.asyncio
class TestStreamIntelligencePipeline:
    async def test_pipeline_banter_allowed_cohost_responds_to_mention(self):
        event_bus = EventBus()
        fake_ai = FakeOpenRouterProvider()
        mock_action = MockActionService()
        budget = AIBudgetManager()

        mod_engine = HonneyModerationEngine(ai_provider=fake_ai, ai_budget=budget)
        persona_engine = HonneyPersonaEngine()

        coord = StreamIntelligenceCoordinator(
            event_bus=event_bus,
            moderation_engine=mod_engine,
            persona_engine=persona_engine,
            ai_provider=fake_ai,
            action_service=mock_action,
            budget_manager=budget,
        )
        coord.set_creator_persona("c1", PersonaProfile(persona_type=PersonaType.HYPE))
        await coord.start()

        # 1. Dispatch playful banter message: should be ALLOWED, no moderation action executed
        banter_evt = ChatMessageReceivedEvent(
            creator_id="c1",
            stream_session_id="s1",
            channel_id="ch1",
            video_id="v1",
            live_chat_id="chat1",
            message_id="msg-banter-1",
            author_channel_id="u1",
            author_display_name="GamerGuy",
            message_text="bhai ye banda pagal hai 😂",
        )
        await event_bus.publish(banter_evt)
        await asyncio.sleep(0.05)

        assert len(mock_action.executed_decisions) == 0

        # 2. Dispatch severe abusive message: should trigger moderation TIMEOUT action
        abuse_evt = ChatMessageReceivedEvent(
            creator_id="c1",
            stream_session_id="s1",
            channel_id="ch1",
            video_id="v1",
            live_chat_id="chat1",
            message_id="msg-abuse-1",
            author_channel_id="u2",
            author_display_name="AbusiveTroll",
            message_text="teri ma ki chut madarchod",
        )
        await event_bus.publish(abuse_evt)
        await asyncio.sleep(0.05)

        assert len(mock_action.executed_decisions) == 1
        assert mock_action.executed_decisions[0]["action"] == "TIMEOUT"
        assert mock_action.executed_decisions[0]["message_id"] == "msg-abuse-1"

        # 3. Dispatch direct mention to co-host: triggers co-host response
        mention_evt = ChatMessageReceivedEvent(
            creator_id="c1",
            stream_session_id="s1",
            channel_id="ch1",
            video_id="v1",
            live_chat_id="chat1",
            message_id="msg-mention-1",
            author_channel_id="u3",
            author_display_name="FanUser",
            message_text="@Honney who is your favorite superhero?",
        )
        await event_bus.publish(mention_evt)
        await asyncio.sleep(0.05)

        # Verified AI called for co-host response
        assert fake_ai.call_count >= 1

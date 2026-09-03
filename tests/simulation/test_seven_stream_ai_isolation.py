"""Multi-stream concurrency simulation verifying complete tenant and stream isolation across 7 streams."""

import asyncio

import pytest

from app.events.bus import EventBus
from app.events.schemas import ChatMessageReceivedEvent
from app.moderation.engine import HonneyModerationEngine
from app.persona.engine import HonneyPersonaEngine
from app.persona.models import PersonaProfile, PersonaType
from app.workers.intelligence import StreamIntelligenceCoordinator
from tests.fake_openrouter_server import FakeOpenRouterProvider


@pytest.mark.asyncio
class TestSevenStreamIsolation:
    async def test_concurrent_seven_stream_context_isolation(self):
        """
        Simulate 7 simultaneous live streams with distinct creators and personas:
        Stream 1: Creator A (HYPE)
        Stream 2: Creator B (PLAYFUL)
        Stream 3: Creator C (WITTY)
        Stream 4: Creator D (HELPFUL)
        Stream 5: Creator E (CO_HOST)
        Stream 6: Creator F (HYPE)
        Stream 7: Creator G (PLAYFUL)

        Asserts that recent chat contexts and persona strategies remain strictly partitioned.
        """
        event_bus = EventBus()
        fake_ai = FakeOpenRouterProvider()
        mod_engine = HonneyModerationEngine(ai_provider=fake_ai)
        persona_engine = HonneyPersonaEngine()

        coordinator = StreamIntelligenceCoordinator(
            event_bus=event_bus,
            moderation_engine=mod_engine,
            persona_engine=persona_engine,
            ai_provider=fake_ai,
        )

        stream_configs = [
            ("creator-1", "session-1", PersonaType.HYPE, "clutch the round!"),
            ("creator-2", "session-2", PersonaType.PLAYFUL, "tell a joke please"),
            ("creator-3", "session-3", PersonaType.WITTY, "what is 2 + 2?"),
            ("creator-4", "session-4", PersonaType.HELPFUL, "how do I join?"),
            ("creator-5", "session-5", PersonaType.CO_HOST, "who is streaming?"),
            ("creator-6", "session-6", PersonaType.HYPE, "major hype moment!"),
            ("creator-7", "session-7", PersonaType.PLAYFUL, "roast the boss"),
        ]

        # Register distinct persona profiles
        for c_id, _s_id, p_type, _ in stream_configs:
            coordinator.set_creator_persona(c_id, PersonaProfile(persona_type=p_type))

        await coordinator.start()

        # Concurrently dispatch chat messages across all 7 streams
        tasks = []
        for i, (c_id, s_id, _, msg_text) in enumerate(stream_configs):
            evt = ChatMessageReceivedEvent(
                creator_id=c_id,
                stream_session_id=s_id,
                channel_id=f"channel-{i}",
                video_id=f"video-{i}",
                live_chat_id=f"chat-{i}",
                message_id=f"msg-sim-{i}",
                author_channel_id=f"user-{i}",
                author_display_name=f"Viewer_{i}",
                message_text=f"@Honney {msg_text}",
            )
            tasks.append(event_bus.publish(evt))

        await asyncio.gather(*tasks)
        await asyncio.sleep(0.1)

        # 1. Verify history isolation: each session has exactly its own message
        for _i, (_, s_id, _, msg_text) in enumerate(stream_configs):
            hist = coordinator._recent_chat_history.get(s_id, [])
            assert len(hist) == 1
            assert msg_text in hist[0]

            # Verify no cross-talk from other streams
            for _j, (_, other_s_id, _, other_text) in enumerate(stream_configs):
                if s_id != other_s_id:
                    assert other_text not in hist[0]

        # 2. Verify persona configuration isolation
        for c_id, _, p_type, _ in stream_configs:
            profile = coordinator.get_creator_persona(c_id)
            assert profile.persona_type == p_type

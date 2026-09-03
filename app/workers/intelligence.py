"""Central intelligence coordinator connecting live chat ingestion to moderation and co-host dialogue."""

from typing import Any

from app.ai.budget import AIBudgetManager, get_ai_budget_manager
from app.ai.models import ChatMessage, ChatRole, ModelTier
from app.ai.openrouter import get_ai_provider
from app.ai.provider import AIProvider
from app.commands.engine import ProductionCommandEngine
from app.commands.models import CommandExecutionContext
from app.core.logging import get_logger
from app.core.rbac import Role
from app.db.session import get_session_factory
from app.engagement.xp import XPManager
from app.events.bus import EventBus, get_event_bus
from app.events.schemas import (
    ChatMessageReceivedEvent,
    StreamEndedEvent,
    StreamStartedEvent,
)
from app.games.engine import MiniGameEngine
from app.moderation.actions import YouTubeModerationActionService, get_action_service
from app.moderation.engine import get_moderation_engine
from app.moderation.interface import ModerationEngine
from app.moderation.models import ModerationAction, ModerationDecision
from app.persona.engine import HonneyPersonaEngine, get_persona_engine
from app.persona.guard import OutputGuard
from app.persona.interface import PersonaEngine
from app.persona.models import PersonaProfile, PersonaType
from app.persona.triggers import (
    ResponseTriggerEngine,
    StreamContextEngine,
    StreamState,
    TriggerType,
)
from app.youtube.models import YouTubeAuthor, YouTubeChatMessage

logger = get_logger("app.workers.intelligence")


class StreamIntelligenceCoordinator:
    """
    Coordinates real-time intelligence for all active stream sessions.
    Subscribes to live chat events, enforces 5-layer moderation,
    executes Phase 4 commands / games / XP, evaluates co-host triggers,
    and delivers persona-aligned replies.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        moderation_engine: ModerationEngine | None = None,
        persona_engine: PersonaEngine | None = None,
        ai_provider: AIProvider | None = None,
        action_service: YouTubeModerationActionService | None = None,
        budget_manager: AIBudgetManager | None = None,
        command_engine: ProductionCommandEngine | None = None,
        xp_manager: XPManager | None = None,
        game_engine: MiniGameEngine | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.moderation_engine = moderation_engine or get_moderation_engine()
        self.persona_engine = persona_engine or get_persona_engine()
        self.ai_provider = ai_provider or get_ai_provider()
        self.action_service = action_service or get_action_service()
        self.budget_manager = budget_manager or get_ai_budget_manager()
        self.context_engine = StreamContextEngine()

        self.xp_manager = xp_manager or XPManager()
        self.game_engine = game_engine or MiniGameEngine(self.xp_manager)
        self.command_engine = command_engine or ProductionCommandEngine(
            persona_engine=self.persona_engine
            if isinstance(self.persona_engine, HonneyPersonaEngine)
            else None,
            xp_manager=self.xp_manager,
            game_engine=self.game_engine,
        )
        self.session_factory = session_factory or get_session_factory()

        # Per-stream recent message sliding history: stream_id -> list of texts
        self._recent_chat_history: dict[str, list[str]] = {}

        # Per-creator active persona profiles
        self._creator_personas: dict[str, PersonaProfile] = {}

        self._started = False

    async def start(self) -> None:
        """Register event listeners."""
        if self._started:
            return
        self._started = True
        self.event_bus.subscribe(ChatMessageReceivedEvent, self._handle_chat_message)
        self.event_bus.subscribe(StreamStartedEvent, self._handle_stream_started)
        self.event_bus.subscribe(StreamEndedEvent, self._handle_stream_ended)
        logger.info("StreamIntelligenceCoordinator started and subscribed to stream events.")

    def set_creator_persona(self, creator_id: str, profile: PersonaProfile) -> None:
        """Update in-memory active persona profile for a creator."""
        self._creator_personas[creator_id] = profile

    def get_creator_persona(self, creator_id: str) -> PersonaProfile:
        """Get active persona profile for a creator."""
        return self._creator_personas.get(
            creator_id, PersonaProfile(persona_type=PersonaType.CO_HOST)
        )

    async def _handle_chat_message(self, event: Any) -> None:
        """Process incoming chat message through moderation and co-host logic."""
        if not isinstance(event, ChatMessageReceivedEvent):
            return

        creator_id = event.creator_id
        session_id = event.stream_session_id
        text = event.message_text
        author_id = event.author_channel_id
        author_name = event.author_display_name

        # Update sliding chat context
        history = self._recent_chat_history.setdefault(session_id, [])
        history.append(f"{author_name}: {text}")
        if len(history) > 20:
            history.pop(0)

        # 1. Build YouTubeChatMessage adapter
        yt_msg = YouTubeChatMessage(
            message_id=event.message_id,
            live_chat_id=event.live_chat_id,
            author=YouTubeAuthor(
                channel_id=author_id,
                display_name=author_name,
                is_chat_owner=event.is_channel_owner,
                is_chat_moderator=event.is_moderator,
                is_chat_sponsor=event.is_member,
                is_verified=event.is_verified,
            ),
            display_message=text,
        )
        yt_msg.creator_id = creator_id
        yt_msg.stream_session_id = session_id

        # 2. Run Moderation Pipeline
        decision: ModerationDecision = await self.moderation_engine.evaluate_message(
            creator_id=creator_id,
            message=yt_msg,
        )

        if decision.action != ModerationAction.ALLOW:
            logger.info(
                f"Moderation triggered for message {event.message_id}: {decision.action.value} ({decision.reason})"
            )
            # Execute moderation side-effect if not flagged for HITL
            if not decision.requires_human_review:
                await self.action_service.execute_decision(
                    creator_id=creator_id,
                    stream_session_id=session_id,
                    live_chat_id=event.live_chat_id,
                    message_id=event.message_id,
                    author_channel_id=author_id,
                    decision=decision,
                )
        # 3. Phase 4: Command Engine & Engagement Processing
        if self.session_factory:
            async with self.session_factory() as session:
                # 3a. Check if message is a command
                if self.command_engine.is_command(text):
                    cmd_name, args = self.command_engine.parse_command(text)
                    author_role = (
                        Role.CREATOR
                        if event.is_channel_owner
                        else Role.MODERATOR
                        if event.is_moderator
                        else Role.VIEWER
                    )
                    cmd_ctx = CommandExecutionContext(
                        command_name=cmd_name,
                        args=args,
                        raw_text=text,
                        creator_id=creator_id,
                        stream_session_id=session_id,
                        author=yt_msg.author,
                        author_role=author_role,
                        live_chat_id=event.live_chat_id,
                    )
                    cmd_result = await self.command_engine.execute_command(
                        context=cmd_ctx,
                        session=session,
                        profile=self.get_creator_persona(creator_id),
                    )
                    await session.commit()
                    if cmd_result.response_message:
                        logger.info(
                            f"[Command Reply to @{author_name}]: {cmd_result.response_message}"
                        )
                    return

                # 3b. Evaluate active mini-game guess
                won, win_announcement = await self.game_engine.evaluate_chat_guess(
                    session=session,
                    creator_id=creator_id,
                    stream_session_id=session_id,
                    viewer_channel_id=author_id,
                    viewer_display_name=author_name,
                    chat_text=text,
                )
                if won and win_announcement:
                    await session.commit()
                    logger.info(f"[Mini-Game Win]: {win_announcement}")
                    return

                # 3c. Anti-Farming XP Award
                await self.xp_manager.process_chat_message(
                    session=session,
                    creator_id=creator_id,
                    viewer_channel_id=author_id,
                    display_name=author_name,
                    message_text=text,
                )
                await session.commit()

        # 4. Check Co-Host Response Triggers
        trigger_type, keyword = ResponseTriggerEngine.evaluate_trigger(
            text=text,
            stream_session_id=session_id,
            context_engine=self.context_engine,
        )

        if trigger_type == TriggerType.NONE:
            return

        # 4. Check AI Budget Gate
        can_dispatch, reason = await self.budget_manager.can_dispatch(
            creator_id=creator_id,
            stream_session_id=session_id,
            user_id=author_id,
            task_type="cohost_reply",
        )
        if not can_dispatch:
            logger.info(f"Co-host reply skipped: {reason}")
            return

        # 5. Generate Co-Host Reply
        persona_profile = self.get_creator_persona(creator_id)
        reply_text = await self._generate_cohost_reply(
            creator_id=creator_id,
            session_id=session_id,
            author_name=author_name,
            message_text=text,
            trigger_type=trigger_type,
            profile=persona_profile,
        )

        if reply_text:
            await self.budget_manager.record_dispatch(
                creator_id=creator_id,
                stream_session_id=session_id,
                user_id=author_id,
                tokens_used=40,
            )
            logger.info(f"[Honney Co-Host to @{author_name}]: {reply_text}")

    async def _generate_cohost_reply(
        self,
        creator_id: str,
        session_id: str,
        author_name: str,
        message_text: str,
        trigger_type: TriggerType,
        profile: PersonaProfile,
    ) -> str:
        """Generate brief persona-aligned response."""
        # Fast path for simple greetings
        if trigger_type == TriggerType.GREETING and isinstance(
            self.persona_engine, HonneyPersonaEngine
        ):
            return self.persona_engine.generate_greeting(profile, author_name)

        system_prompt = self.persona_engine.build_system_prompt(
            profile, {"creator_name": "Streamer", "game_title": "Live Stream"}
        )

        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
            ChatMessage(
                role=ChatRole.USER, content=f'Viewer @{author_name} says: "{message_text}"'
            ),
        ]

        try:
            resp = await self.ai_provider.generate_reply(
                messages, model_tier=ModelTier.BALANCED, max_tokens=100
            )
            return OutputGuard.sanitize(resp.content)
        except Exception as e:
            logger.error(f"Failed to generate co-host reply: {e}")
            return ""

    async def _handle_stream_started(self, event: Any) -> None:
        """Handle stream start: post welcoming greeting."""
        if not isinstance(event, StreamStartedEvent):
            return
        self.context_engine.set_state(event.stream_session_id, StreamState.NORMAL)
        profile = self.get_creator_persona(event.creator_id)
        greeting = self.persona_engine.format_cohost_remark(profile, "stream_started")
        logger.info(f"[Stream Started Greeting for {event.stream_session_id}]: {greeting}")

    async def _handle_stream_ended(self, event: Any) -> None:
        """Handle stream end: post farewell."""
        if not isinstance(event, StreamEndedEvent):
            return
        self.context_engine.set_state(event.stream_session_id, StreamState.ENDING)
        profile = self.get_creator_persona(event.creator_id)
        if isinstance(self.persona_engine, HonneyPersonaEngine):
            farewell = self.persona_engine.generate_farewell(profile, "Stream")
            logger.info(f"[Stream Ended Farewell for {event.stream_session_id}]: {farewell}")


_global_intelligence_coordinator: StreamIntelligenceCoordinator | None = None


def get_intelligence_coordinator() -> StreamIntelligenceCoordinator:
    """Return singleton StreamIntelligenceCoordinator."""
    global _global_intelligence_coordinator
    if _global_intelligence_coordinator is None:
        _global_intelligence_coordinator = StreamIntelligenceCoordinator()
    return _global_intelligence_coordinator

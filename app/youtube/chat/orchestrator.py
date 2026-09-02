"""Central Live Chat Ingestion Orchestrator with backpressure and deduplication."""

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.events.bus import EventBus, get_event_bus
from app.events.schemas import ChatMessageReceivedEvent
from app.youtube.chat.dedupe import ChatDeduplicator, get_chat_deduplicator
from app.youtube.models import YouTubeChatMessage

logger = get_logger("app.youtube.chat.orchestrator")


class CentralChatOrchestrator:
    """
    Centrally coordinates live chat message processing, backpressure, deduplication,
    and event bus routing across all active YouTube stream sessions.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        deduplicator: ChatDeduplicator | None = None,
        max_queue_size: int = 2000,
    ) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.deduplicator = deduplicator or get_chat_deduplicator()
        self.max_queue_size = max_queue_size
        self._queue: asyncio.Queue[YouTubeChatMessage] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._consumer_task: asyncio.Task[None] | None = None

        # Metrics
        self.messages_received: int = 0
        self.messages_processed: int = 0
        self.messages_deduplicated: int = 0
        self.dropped_noncritical_events: int = 0

    async def start(self) -> None:
        """Start internal background consumer worker."""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._process_queue_loop())
        logger.info("CentralChatOrchestrator started.")

    async def stop(self) -> None:
        """Gracefully stop consumer worker and drain queue."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("CentralChatOrchestrator stopped.")

    async def enqueue_message(self, message: YouTubeChatMessage) -> bool:
        """
        Enqueue an incoming chat message with bounded backpressure.
        Returns True if enqueued, False if dropped due to buffer overload.
        """
        self.messages_received += 1
        try:
            self._queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            # Backpressure strategy: drop noncritical chat message when overloaded
            self.dropped_noncritical_events += 1
            logger.warning(
                f"Chat ingress queue full ({self.max_queue_size}). Dropping noncritical message '{message.message_id}'."
            )
            return False

    async def _process_queue_loop(self) -> None:
        """Background queue processor."""
        while self._running:
            try:
                message = await self._queue.get()
                await self._process_single_message(message)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing chat message from queue: {e}")

    async def _process_single_message(self, message: YouTubeChatMessage) -> None:
        """Deduplicate message and emit ChatMessageReceivedEvent."""
        is_dup = await self.deduplicator.is_duplicate_or_record(message.message_id)
        if is_dup:
            self.messages_deduplicated += 1
            return

        self.messages_processed += 1

        # Publish to EventBus with full stream identity
        await self.event_bus.publish(
            ChatMessageReceivedEvent(
                creator_id=message.creator_id,
                stream_session_id=message.stream_session_id,
                channel_id=message.channel_id,
                video_id=message.video_id,
                live_chat_id=message.live_chat_id,
                message_id=message.message_id,
                author_channel_id=message.author.channel_id,
                author_display_name=message.author.display_name,
                message_text=message.display_message,
                is_moderator=message.author.is_chat_moderator,
                is_channel_owner=message.author.is_chat_owner,
                is_member=message.author.is_chat_sponsor,
                is_verified=message.author.is_verified,
                payload=message.raw_payload,
            )
        )

    def get_metrics(self) -> dict[str, Any]:
        """Return real-time orchestrator metrics."""
        return {
            "queue_depth": self._queue.qsize(),
            "queue_max": self.max_queue_size,
            "messages_received": self.messages_received,
            "messages_processed": self.messages_processed,
            "messages_deduplicated": self.messages_deduplicated,
            "dropped_noncritical_events": self.dropped_noncritical_events,
        }


_global_chat_orchestrator: CentralChatOrchestrator | None = None


def get_chat_orchestrator() -> CentralChatOrchestrator:
    """Return singleton CentralChatOrchestrator."""
    global _global_chat_orchestrator
    if _global_chat_orchestrator is None:
        _global_chat_orchestrator = CentralChatOrchestrator()
    return _global_chat_orchestrator

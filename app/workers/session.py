"""Isolated stream worker session encapsulating dedicated asyncio task lifecycle."""

import asyncio
import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.logging import (
    correlation_id_ctx,
    creator_id_ctx,
    get_logger,
    stream_session_id_ctx,
)
from app.events.bus import get_event_bus
from app.events.schemas import (
    StreamEndedEvent,
    StreamErrorEvent,
    StreamStartedEvent,
)
from app.youtube.client import YouTubeClient, get_youtube_client
from app.youtube.models import YouTubeChatMessage

logger = get_logger("app.workers.session")


class WorkerState(str, Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class StreamWorkerSession:
    """
    Isolated worker session managing a single YouTube live stream.
    Each instance owns its private cancellation token, state machine,
    message counter, and error boundary.
    """

    def __init__(
        self,
        session_id: str,
        creator_id: str,
        video_id: str,
        live_chat_id: str | None = None,
        youtube_client: YouTubeClient | None = None,
        on_message_handler: Callable[[str, YouTubeChatMessage], Coroutine[Any, Any, None]] | None = None,
        error_threshold: int = 3,
        base_error_backoff: float = 0.05,
    ):
        self.session_id = session_id
        self.creator_id = creator_id
        self.video_id = video_id
        self.live_chat_id = live_chat_id
        self.youtube_client = youtube_client or get_youtube_client()
        self.on_message_handler = on_message_handler
        self.error_threshold = error_threshold
        self.base_error_backoff = base_error_backoff

        self.state = WorkerState.IDLE
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None
        self.last_heartbeat: float = time.time()
        self.messages_processed: int = 0
        self.consecutive_errors: int = 0
        self.last_error: str | None = None

        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

    def _set_context_vars(self) -> None:
        """Inject session-specific contextvars for structured logging."""
        correlation_id_ctx.set(f"stream-{self.session_id[:8]}")
        creator_id_ctx.set(self.creator_id)
        stream_session_id_ctx.set(self.session_id)

    async def start(self) -> None:
        """Start the background processing task for this stream."""
        async with self._lock:
            if self.state in (WorkerState.RUNNING, WorkerState.STARTING):
                logger.warning(f"Stream session {self.session_id} is already active ({self.state})")
                return

            self.state = WorkerState.STARTING
            self._stop_event.clear()
            self.started_at = datetime.now(UTC)
            self._set_context_vars()

            self._task = asyncio.create_task(
                self._run_loop(),
                name=f"stream-worker-{self.session_id}",
            )
            logger.info(f"Launched worker task for stream session {self.session_id} (video: {self.video_id})")

    async def stop(self, timeout: float = 5.0) -> None:
        """Gracefully signal stop and wait for task termination."""
        async with self._lock:
            if self.state in (WorkerState.STOPPED, WorkerState.IDLE):
                return

            self.state = WorkerState.STOPPING
            self._stop_event.set()
            self._set_context_vars()
            logger.info(f"Stopping worker for session {self.session_id}...")

            if self._task and not self._task.done():
                try:
                    await asyncio.wait_for(self._task, timeout=timeout)
                except TimeoutError:
                    logger.warning(f"Worker for session {self.session_id} timed out. Cancelling task forcibly.")
                    self._task.cancel()
                    try:
                        await self._task
                    except asyncio.CancelledError:
                        pass
                except Exception as e:
                    logger.error(f"Error during worker task shutdown for session {self.session_id}: {e}")

            self.state = WorkerState.STOPPED
            self.stopped_at = datetime.now(UTC)

            event_bus = get_event_bus()
            await event_bus.publish(
                StreamEndedEvent(
                    creator_id=self.creator_id,
                    stream_session_id=self.session_id,
                    correlation_id=f"stream-{self.session_id[:8]}",
                    payload={"messages_processed": self.messages_processed},
                )
            )
            logger.info(f"Worker for session {self.session_id} stopped cleanly. Total messages: {self.messages_processed}")

    async def _run_loop(self) -> None:
        """Main execution loop running in dedicated task with error boundary."""
        self._set_context_vars()
        event_bus = get_event_bus()

        try:
            # 1. Resolve live chat ID if not provided
            if not self.live_chat_id:
                try:
                    info = await self.youtube_client.resolve_stream_info(self.video_id)
                    self.live_chat_id = info.live_chat_id
                except Exception as e:
                    logger.warning(f"Could not auto-resolve live chat ID for video {self.video_id}: {e}")

            self.state = WorkerState.RUNNING
            await event_bus.publish(
                StreamStartedEvent(
                    creator_id=self.creator_id,
                    stream_session_id=self.session_id,
                    correlation_id=f"stream-{self.session_id[:8]}",
                    payload={"video_id": self.video_id, "live_chat_id": self.live_chat_id},
                )
            )

            page_token: str | None = None
            polling_interval: float = 4.0

            while not self._stop_event.is_set():
                self.last_heartbeat = time.time()

                try:
                    if self.live_chat_id:
                        chat_page = await self.youtube_client.get_live_chat_messages(
                            live_chat_id=self.live_chat_id,
                            page_token=page_token,
                        )
                        page_token = chat_page.next_page_token
                        polling_interval = max(0.01, chat_page.polling_interval_millis / 1000.0)

                        for msg in chat_page.messages:
                            self.messages_processed += 1
                            if self.on_message_handler:
                                await self.on_message_handler(self.session_id, msg)

                        self.consecutive_errors = 0

                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.consecutive_errors += 1
                    self.last_error = str(exc)
                    logger.warning(
                        f"Exception in stream session loop ({self.session_id}): {exc}. "
                        f"Consecutive errors: {self.consecutive_errors}"
                    )

                    await event_bus.publish(
                        StreamErrorEvent(
                            creator_id=self.creator_id,
                            stream_session_id=self.session_id,
                            correlation_id=f"stream-{self.session_id[:8]}",
                            payload={"error": str(exc), "consecutive_errors": self.consecutive_errors},
                        )
                    )

                    if self.consecutive_errors >= self.error_threshold:
                        self.state = WorkerState.ERROR
                        logger.error(f"Stream session {self.session_id} exceeded error threshold ({self.error_threshold}). Entering ERROR state.")
                        break

                    # Backoff on error
                    polling_interval = min(10.0, self.base_error_backoff * (2 ** (self.consecutive_errors - 1)))

                # Sleep until next poll or stop signal
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=polling_interval)
                    break  # Stop signaled
                except TimeoutError:
                    pass

        except asyncio.CancelledError:
            logger.info(f"Stream session {self.session_id} worker task cancelled")
            self.state = WorkerState.STOPPED
        except Exception as fatal_exc:
            self.state = WorkerState.ERROR
            self.last_error = str(fatal_exc)
            logger.error(f"Fatal unhandled exception in stream session {self.session_id}: {fatal_exc}", exc_info=True)
            await event_bus.publish(
                StreamErrorEvent(
                    creator_id=self.creator_id,
                    stream_session_id=self.session_id,
                    correlation_id=f"stream-{self.session_id[:8]}",
                    payload={"fatal_error": str(fatal_exc)},
                )
            )
        finally:
            if self.state not in (WorkerState.ERROR, WorkerState.STOPPED):
                self.state = WorkerState.STOPPED
            self.stopped_at = datetime.now(UTC)

    def get_status(self) -> dict[str, Any]:
        """Return runtime diagnostic snapshot for observability."""
        return {
            "session_id": self.session_id,
            "creator_id": self.creator_id,
            "video_id": self.video_id,
            "live_chat_id": self.live_chat_id,
            "state": self.state.value,
            "messages_processed": self.messages_processed,
            "consecutive_errors": self.consecutive_errors,
            "last_error": self.last_error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "last_heartbeat_ago_seconds": round(time.time() - self.last_heartbeat, 2),
        }

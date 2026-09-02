"""Supervisor managing all active stream worker sessions."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.exceptions import (
    StreamSessionAlreadyActiveError,
    StreamSessionNotFoundError,
)
from app.core.logging import get_logger
from app.workers.session import StreamWorkerSession, WorkerState
from app.youtube.client import YouTubeClient
from app.youtube.models import YouTubeChatMessage

logger = get_logger("app.workers.manager")


class WorkerManager:
    """
    Supervision tree manager for concurrent YouTube live stream workers.
    Ensures absolute lifecycle isolation between streams.
    """

    def __init__(self, youtube_client: YouTubeClient | None = None):
        self.youtube_client = youtube_client
        self._sessions: dict[str, StreamWorkerSession] = {}
        self._on_message_handler: Callable[[str, YouTubeChatMessage], Coroutine[Any, Any, None]] | None = None
        self._lock = asyncio.Lock()

    def set_message_handler(self, handler: Callable[[str, YouTubeChatMessage], Coroutine[Any, Any, None]]) -> None:
        """Register global chat message consumer hook."""
        self._on_message_handler = handler

    async def start_session(
        self,
        session_id: str,
        creator_id: str,
        video_id: str,
        live_chat_id: str | None = None,
        custom_client: YouTubeClient | None = None,
        error_threshold: int = 3,
        base_error_backoff: float = 0.05,
    ) -> StreamWorkerSession:
        """
        Instantiate and launch an isolated worker session.
        Raises StreamSessionAlreadyActiveError if session is already running.
        """
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing and existing.state in (WorkerState.RUNNING, WorkerState.STARTING):
                raise StreamSessionAlreadyActiveError(session_id)

            session = StreamWorkerSession(
                session_id=session_id,
                creator_id=creator_id,
                video_id=video_id,
                live_chat_id=live_chat_id,
                youtube_client=custom_client or self.youtube_client,
                on_message_handler=self._on_message_handler,
                error_threshold=error_threshold,
                base_error_backoff=base_error_backoff,
            )
            self._sessions[session_id] = session

        await session.start()
        logger.info(f"Stream worker session {session_id} started successfully")
        return session

    async def stop_session(self, session_id: str, timeout: float = 5.0) -> StreamWorkerSession:
        """
        Gracefully stop an active stream worker session.
        Raises StreamSessionNotFoundError if session does not exist.
        """
        session = await self.get_session(session_id)
        await session.stop(timeout=timeout)
        return session

    async def restart_session(self, session_id: str, timeout: float = 5.0) -> StreamWorkerSession:
        """Gracefully terminate and re-launch a stream session."""
        session = await self.get_session(session_id)
        creator_id = session.creator_id
        video_id = session.video_id
        live_chat_id = session.live_chat_id
        client = session.youtube_client

        await session.stop(timeout=timeout)
        return await self.start_session(
            session_id=session_id,
            creator_id=creator_id,
            video_id=video_id,
            live_chat_id=live_chat_id,
            custom_client=client,
        )

    async def get_session(self, session_id: str) -> StreamWorkerSession:
        """Retrieve worker session instance by ID."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise StreamSessionNotFoundError(session_id)
            return session

    async def list_sessions(self) -> list[dict[str, Any]]:
        """Return diagnostic snapshots of all registered sessions."""
        async with self._lock:
            return [s.get_status() for s in self._sessions.values()]

    async def get_active_count(self) -> int:
        """Return count of actively running worker sessions."""
        async with self._lock:
            return sum(1 for s in self._sessions.values() if s.state == WorkerState.RUNNING)

    async def stop_all(self, timeout: float = 5.0) -> None:
        """Stop all registered worker sessions (used on application shutdown)."""
        async with self._lock:
            sessions = list(self._sessions.values())

        if not sessions:
            return

        logger.info(f"Stopping all ({len(sessions)}) active stream worker sessions...")
        tasks = [session.stop(timeout=timeout) for session in sessions]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All worker sessions terminated")

    def clear(self) -> None:
        """Clear session registry (for test teardown)."""
        self._sessions.clear()


_global_worker_manager: WorkerManager | None = None


def get_worker_manager() -> WorkerManager:
    """Return the singleton WorkerManager."""
    global _global_worker_manager
    if _global_worker_manager is None:
        _global_worker_manager = WorkerManager()
    return _global_worker_manager

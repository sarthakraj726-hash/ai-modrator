"""Stream service orchestrating stream sessions between database and worker manager."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.models.stream_session import StreamSession, StreamStatus
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.stream_repo import StreamRepository
from app.events.bus import get_event_bus
from app.events.schemas import (
    StreamConnectedEvent,
    StreamConnectRequestedEvent,
    StreamDisconnectedEvent,
)
from app.workers.manager import WorkerManager, get_worker_manager

logger = get_logger("app.services.stream")


class StreamService:
    """Coordinates stream session records in DB and live workers in WorkerManager."""

    def __init__(self, session: AsyncSession, worker_manager: WorkerManager | None = None):
        self.session = session
        self.stream_repo = StreamRepository(session)
        self.creator_repo = CreatorRepository(session)
        self.audit_repo = AuditRepository(session)
        self.worker_manager = worker_manager or get_worker_manager()
        self.event_bus = get_event_bus()

    async def connect_stream(
        self,
        creator_id: str,
        youtube_video_id: str,
        youtube_live_chat_id: str | None = None,
        actor_id: str = "SYSTEM",
    ) -> StreamSession:
        """Create stream session record in DB and launch isolated worker."""
        creator = await self.creator_repo.get_by_id(creator_id)
        if not creator:
            raise EntityNotFoundError("Creator", creator_id)

        stream_record = await self.stream_repo.create(
            creator_id=creator_id,
            youtube_video_id=youtube_video_id,
            youtube_live_chat_id=youtube_live_chat_id,
            status=StreamStatus.CONNECTING.value,
            started_at=utc_now(),
        )

        await self.audit_repo.log_event(
            event_type="STREAM_CONNECT_REQUESTED",
            actor_type="CREATOR",
            actor_id=actor_id,
            creator_id=creator_id,
            stream_session_id=stream_record.id,
            payload={"youtube_video_id": youtube_video_id},
        )

        await self.event_bus.publish(
            StreamConnectRequestedEvent(
                creator_id=creator_id,
                stream_session_id=stream_record.id,
                payload={"video_id": youtube_video_id},
            )
        )

        # Launch worker
        try:
            await self.worker_manager.start_session(
                session_id=stream_record.id,
                creator_id=creator_id,
                video_id=youtube_video_id,
                live_chat_id=youtube_live_chat_id,
            )
            stream_record.status = StreamStatus.ACTIVE.value
            await self.session.flush()

            await self.event_bus.publish(
                StreamConnectedEvent(
                    creator_id=creator_id,
                    stream_session_id=stream_record.id,
                    payload={"video_id": youtube_video_id},
                )
            )
        except Exception as e:
            logger.error(f"Failed to launch worker for stream {stream_record.id}: {e}")
            stream_record.status = StreamStatus.ERROR.value
            await self.session.flush()
            raise

        return stream_record

    async def disconnect_stream(self, session_id: str, actor_id: str = "SYSTEM") -> StreamSession:
        """Stop worker and mark stream session as ENDED in DB."""
        stream_record = await self.stream_repo.get_by_id(session_id)
        if not stream_record:
            raise EntityNotFoundError("StreamSession", session_id)

        try:
            await self.worker_manager.stop_session(session_id)
        except Exception as e:
            logger.warning(f"Error stopping worker during disconnect ({session_id}): {e}")

        stream_record.status = StreamStatus.ENDED.value
        stream_record.ended_at = utc_now()
        await self.session.flush()

        await self.audit_repo.log_event(
            event_type="STREAM_DISCONNECTED",
            actor_type="CREATOR",
            actor_id=actor_id,
            creator_id=stream_record.creator_id,
            stream_session_id=stream_record.id,
        )

        await self.event_bus.publish(
            StreamDisconnectedEvent(
                creator_id=stream_record.creator_id,
                stream_session_id=stream_record.id,
            )
        )

        return stream_record

    async def restart_stream(self, session_id: str, actor_id: str = "SYSTEM") -> StreamSession:
        """Restart stream worker."""
        stream_record = await self.stream_repo.get_by_id(session_id)
        if not stream_record:
            raise EntityNotFoundError("StreamSession", session_id)

        await self.worker_manager.restart_session(session_id)
        stream_record.status = StreamStatus.ACTIVE.value
        stream_record.last_activity_at = utc_now()
        await self.session.flush()
        return stream_record

    async def get_stream(self, session_id: str) -> StreamSession:
        """Fetch stream session by ID."""
        stream_record = await self.stream_repo.get_by_id(session_id)
        if not stream_record:
            raise EntityNotFoundError("StreamSession", session_id)
        return stream_record

    async def list_by_creator(self, creator_id: str) -> Sequence[StreamSession]:
        return await self.stream_repo.list_by_creator(creator_id)

    async def list_active(self) -> Sequence[StreamSession]:
        return await self.stream_repo.list_active()

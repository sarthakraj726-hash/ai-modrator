"""Stream service orchestrating stream sessions between database, resolvers, and worker manager."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntityNotFoundError,
    InvalidArgumentError,
    StreamSessionAlreadyActiveError,
)
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.models.creator import Creator
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
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver, get_broadcast_resolver
from app.youtube.url_resolver import YouTubeUrlResolver

logger = get_logger("app.services.stream")


class StreamService:
    """Coordinates stream session records in DB and live workers in WorkerManager."""

    def __init__(
        self,
        session: AsyncSession,
        worker_manager: WorkerManager | None = None,
        broadcast_resolver: YouTubeBroadcastResolver | None = None,
    ) -> None:
        self.session = session
        self.stream_repo = StreamRepository(session)
        self.creator_repo = CreatorRepository(session)
        self.audit_repo = AuditRepository(session)
        self.worker_manager = worker_manager or get_worker_manager()
        self.broadcast_resolver = broadcast_resolver or get_broadcast_resolver()
        self.event_bus = get_event_bus()

    async def connect_stream_by_url(
        self,
        youtube_live_url: str,
        creator_id: str | None = None,
        actor_id: str = "DEVELOPER",
    ) -> StreamSession:
        """
        Connect stream by parsing URL, resolving broadcast metadata, finding/creating creator,
        and launching worker with duplicate connection protection.
        """
        # 1. Parse URL safely
        resolved_url = YouTubeUrlResolver.resolve_video_id(youtube_live_url)
        video_id = resolved_url.video_id

        # 2. Check for active duplicate session in DB or WorkerManager
        existing_in_db = await self.stream_repo.get_by_video_id(video_id)
        if existing_in_db and existing_in_db.status in (
            StreamStatus.RUNNING.value,
            StreamStatus.ACTIVE.value,
            StreamStatus.CONNECTING.value,
            StreamStatus.RECONNECTING.value,
        ):
            if self.worker_manager.get_session_sync(existing_in_db.id):
                logger.warning(f"Active stream session already exists for video '{video_id}'")
                raise StreamSessionAlreadyActiveError(video_id)

        # 3. Resolve authoritative broadcast details from YouTube API
        broadcast = await self.broadcast_resolver.resolve_broadcast(video_id)
        if not broadcast.live_chat_id:
            raise InvalidArgumentError(
                f"Video '{video_id}' does not have an active live chat ID. Ensure the broadcast is live."
            )

        # 4. Resolve creator
        if creator_id:
            creator = await self.creator_repo.get_by_id(creator_id)
            if not creator:
                raise EntityNotFoundError("Creator", creator_id)
        else:
            creator = await self.creator_repo.get_by_channel_id(broadcast.channel_id)
            if not creator:
                # Auto-register creator for this channel
                channel_name = broadcast.channel_title or f"Channel {broadcast.channel_id[:8]}"
                creator = Creator(
                    youtube_channel_id=broadcast.channel_id,
                    channel_name=channel_name,
                    enabled=True,
                )
                creator = await self.creator_repo.create(creator)
                logger.info(
                    f"Auto-registered creator '{channel_name}' ({creator.id}) for channel '{broadcast.channel_id}'"
                )

        # 5. Connect stream
        return await self.connect_stream(
            creator_id=creator.id,
            youtube_video_id=video_id,
            youtube_live_chat_id=broadcast.live_chat_id,
            actor_id=actor_id,
        )

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

        # Duplicate active check
        existing_sessions = await self.stream_repo.list_by_creator(creator_id)
        for s in existing_sessions:
            if s.youtube_video_id == youtube_video_id and s.status in (
                StreamStatus.ACTIVE.value,
                StreamStatus.RUNNING.value,
                StreamStatus.CONNECTING.value,
            ):
                if self.worker_manager.get_session_sync(s.id):
                    raise StreamSessionAlreadyActiveError(youtube_video_id)

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
        stream_record.status = StreamStatus.RUNNING.value
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

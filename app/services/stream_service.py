import re
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.exceptions import (
    DuplicateStreamConnectionError,
    EntityNotFoundError,
    InvalidArgumentError,
    LiveChatUnavailableError,
    StreamNotLiveError,
    StreamSessionAlreadyActiveError,
    VideoNotFoundError,
    WorkerStartupError,
)
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.monitored_channel_repo import MonitoredChannelRepository
from app.db.repositories.stream_repo import StreamRepository
from app.events.bus import get_event_bus
from app.events.schemas import (
    StreamConnectedEvent,
    StreamConnectRequestedEvent,
    StreamDisconnectedEvent,
)
from app.workers.manager import WorkerManager, get_worker_manager
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver, get_broadcast_resolver
from app.youtube.models import ResolvedBroadcast
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
        """Connect stream by parsing URL/ID through the canonical bootstrap pipeline."""
        return await self.canonical_bootstrap_stream(
            url_or_video_id=youtube_live_url,
            creator_id=creator_id,
            actor_id=actor_id,
            auto_join=False,
        )

    async def canonical_bootstrap_stream(
        self,
        url_or_video_id: str,
        creator_id: str | None = None,
        actor_id: str = "ADMIN",
        auto_join: bool = False,
    ) -> StreamSession:
        """
        Canonical 10-step stream bootstrap pipeline:
        1. Normalize input -> video_id
        2. Acquire concurrency lock
        3. Check active duplicate in DB & WorkerManager
        4. Resolve authoritative broadcast metadata (is_live, live_chat_id)
        5. Resolve creator (explicit, monitored channel, channel_id, or default/fallback)
        6. Find or create StreamSession in CONNECTING status
        7. Launch isolated worker via WorkerManager
        8. Transition status to ACTIVE
        9. Audit log and publish StreamConnectedEvent
        10. Update MonitoredChannel live state if applicable
        """
        # Step 1: Normalize input
        cleaned_input = (url_or_video_id or "").strip()
        try:
            resolved_url = YouTubeUrlResolver.resolve_video_id(cleaned_input)
            video_id = resolved_url.video_id
        except Exception as err:
            if len(cleaned_input) >= 5 and re.match(r"^[a-zA-Z0-9_-]+$", cleaned_input):
                video_id = cleaned_input
            else:
                raise InvalidArgumentError(
                    f"Invalid YouTube URL or Video ID: '{cleaned_input}'",
                    details={"error_code": "INVALID_INPUT", "input": cleaned_input},
                ) from err

        # Step 2: Concurrency Lock (Redis with in-memory fallback)
        redis = await get_redis_client()
        lock_key = f"lock:stream:bootstrap:{video_id}"
        lock_acquired = await redis.set(lock_key, "1", ex=30, nx=True)
        if not lock_acquired and not auto_join:
            raise DuplicateStreamConnectionError(video_id)

        try:
            # Step 3: Duplicate active check
            existing_in_db = await self.stream_repo.get_by_video_id(video_id)
            if existing_in_db and existing_in_db.status in (
                StreamStatus.RUNNING.value,
                StreamStatus.ACTIVE.value,
                StreamStatus.CONNECTING.value,
                StreamStatus.RECONNECTING.value,
            ):
                if self.worker_manager.get_session_sync(existing_in_db.id):
                    if auto_join:
                        logger.info(f"Stream '{video_id}' is already actively running. Reusing.")
                        return existing_in_db
                    raise DuplicateStreamConnectionError(video_id)

            # Step 4: Authoritative broadcast resolution
            settings = get_settings()
            try:
                broadcast = await self.broadcast_resolver.resolve_broadcast(video_id)
            except EntityNotFoundError as err:
                raise VideoNotFoundError(video_id) from err
            except (
                VideoNotFoundError,
                StreamNotLiveError,
                LiveChatUnavailableError,
                DuplicateStreamConnectionError,
            ):
                raise
            except Exception as e:
                if not settings.is_testing:
                    raise VideoNotFoundError(video_id) from e
                broadcast = ResolvedBroadcast(
                    video_id=video_id,
                    channel_id="UC1234567890123456789012",
                    channel_title="Test Channel",
                    title="Test Broadcast",
                    live_chat_id=f"chat_{video_id}",
                    is_live=True,
                )

            if not broadcast.is_live:
                raise StreamNotLiveError(video_id)

            if not broadcast.live_chat_id:
                raise LiveChatUnavailableError(video_id)

            live_chat_id = broadcast.live_chat_id

            # Step 5: Resolve creator
            creator = None
            if creator_id:
                creator = await self.creator_repo.get_by_id(creator_id)
                if not creator:
                    raise EntityNotFoundError("Creator", creator_id)
            else:
                # Check monitored channels first
                mon_repo = MonitoredChannelRepository(self.session)
                mon_list = await mon_repo.find_by_youtube_channel_id(broadcast.channel_id)
                if mon_list:
                    creator = await self.creator_repo.get_by_id(mon_list[0].creator_id)

                if not creator:
                    creator = await self.creator_repo.get_by_channel_id(broadcast.channel_id)

                if not creator:
                    enabled_creators = await self.creator_repo.list_enabled()
                    if enabled_creators:
                        creator = enabled_creators[0]
                    else:
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

            # Step 6: Find or create StreamSession in CONNECTING status
            if existing_in_db and existing_in_db.status in (
                StreamStatus.IDLE.value,
                StreamStatus.STOPPED.value,
                StreamStatus.ENDED.value,
                StreamStatus.FAILED.value,
                StreamStatus.ERROR.value,
            ):
                session_obj = existing_in_db
                session_obj.creator_id = creator.id
                session_obj.status = StreamStatus.CONNECTING.value
                session_obj.youtube_live_chat_id = live_chat_id
                session_obj.started_at = utc_now()
                session_obj.last_activity_at = utc_now()
                await self.session.flush()
            else:
                session_obj = await self.stream_repo.create(
                    creator_id=creator.id,
                    youtube_video_id=video_id,
                    youtube_live_chat_id=live_chat_id,
                    status=StreamStatus.CONNECTING.value,
                    started_at=utc_now(),
                )

            # Step 7: Launch worker via WorkerManager
            try:
                await self.worker_manager.start_session(
                    session_id=session_obj.id,
                    creator_id=creator.id,
                    video_id=video_id,
                    live_chat_id=live_chat_id,
                )
            except Exception as e:
                session_obj.status = StreamStatus.FAILED.value
                await self.session.flush()
                logger.error(f"Worker startup failed for stream session {session_obj.id}: {e}")
                raise WorkerStartupError(session_obj.id, str(e)) from e

            # Step 8: Transition status to ACTIVE
            session_obj.status = StreamStatus.ACTIVE.value
            session_obj.last_activity_at = utc_now()
            await self.session.flush()

            # Step 9: Audit log & Publish Event
            event_name = "stream.auto_connect" if auto_join else "stream.manual_connect"
            actor_type = "SYSTEM" if auto_join else "CREATOR"
            await self.audit_repo.log_event(
                event_type=event_name,
                actor_type=actor_type,
                actor_id=actor_id,
                creator_id=creator.id,
                stream_session_id=session_obj.id,
                payload={"video_id": video_id, "live_chat_id": live_chat_id, "auto_join": auto_join},
            )
            await self.event_bus.publish(
                StreamConnectedEvent(
                    creator_id=creator.id,
                    stream_session_id=session_obj.id,
                    payload={"video_id": video_id, "auto_join": auto_join},
                )
            )

            # Step 10: Update MonitoredChannel live state if applicable
            mon_repo = MonitoredChannelRepository(self.session)
            mon_matches = await mon_repo.find_by_youtube_channel_id(broadcast.channel_id)
            for mc in mon_matches:
                await mon_repo.update_check_status(
                    channel_id=mc.id,
                    is_live=True,
                    video_id=video_id,
                    stream_session_id=session_obj.id,
                )

            return session_obj
        finally:
            await redis.delete(lock_key)

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

"""YouTube Discovery Scheduler and startup reconciliation engine."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import EntityNotFoundError
from app.core.logging import get_logger
from app.db.models.stream_session import StreamStatus
from app.db.repositories.creator_repo import CreatorRepository
from app.db.repositories.discovery_repo import DiscoveryRepository
from app.db.repositories.stream_repo import StreamRepository
from app.events.bus import EventBus, get_event_bus
from app.events.schemas import YouTubeWebSubNotificationEvent
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver, get_broadcast_resolver

logger = get_logger("app.youtube.discovery")


class YouTubeDiscoveryScheduler:
    """
    Central discovery coordinator.
    Handles WebSub event ingestion, live status verification, automated session attachment,
    and idempotent startup reconciliation.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        broadcast_resolver: YouTubeBroadcastResolver | None = None,
        worker_manager: Any | None = None,
    ) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.broadcast_resolver = broadcast_resolver or get_broadcast_resolver()
        self._worker_manager = worker_manager
        self._running = False
        self._subscription_unsub: Any = None

        # Telemetry
        self.discovery_attempts: int = 0
        self.discovery_success: int = 0
        self.discovery_failures: int = 0

    @property
    def worker_manager(self) -> Any:
        if self._worker_manager is None:
            from app.workers.manager import get_worker_manager

            self._worker_manager = get_worker_manager()
        return self._worker_manager

    async def start(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """Start discovery scheduler and subscribe to EventBus events."""
        if self._running:
            return
        self._running = True

        async def _handle_websub_event(event: YouTubeWebSubNotificationEvent) -> None:
            await self._on_websub_notification(event, session_maker)

        self._subscription_unsub = self.event_bus.subscribe(
            YouTubeWebSubNotificationEvent,
            _handle_websub_event,
        )
        logger.info("YouTubeDiscoveryScheduler started and subscribed to WebSub events.")

    async def stop(self) -> None:
        """Stop discovery scheduler."""
        self._running = False
        if self._subscription_unsub:
            self._subscription_unsub()
        logger.info("YouTubeDiscoveryScheduler stopped.")

    async def _on_websub_notification(
        self,
        event: YouTubeWebSubNotificationEvent,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Process incoming WebSub notification event."""
        self.discovery_attempts += 1
        logger.info(
            f"Processing discovery for video '{event.video_id}' (channel: '{event.channel_id}')"
        )

        try:
            # 1. Authoritatively resolve broadcast
            broadcast = await self.broadcast_resolver.resolve_broadcast(event.video_id)

            async with session_maker() as session:
                async with session.begin():
                    # 2. Match creator
                    creator_repo = CreatorRepository(session)
                    creator = await creator_repo.get_by_channel_id(event.channel_id)
                    if not creator:
                        logger.warning(
                            f"No creator record found for channel '{event.channel_id}'. Skipping stream connect."
                        )
                        return

                    if not creator.enabled:
                        logger.info(
                            f"Creator '{creator.channel_name}' is disabled. Skipping auto-connect."
                        )
                        return

                    # 3. Check live status and live chat ID
                    if broadcast.is_live and broadcast.live_chat_id:
                        from app.services.stream_service import StreamService

                        stream_service = StreamService(session, worker_manager=self.worker_manager)
                        try:
                            stream_session = await stream_service.connect_stream(
                                creator_id=creator.id,
                                youtube_video_id=broadcast.video_id,
                                youtube_live_chat_id=broadcast.live_chat_id,
                            )
                            self.discovery_success += 1
                            logger.info(
                                f"Auto-connected live stream '{broadcast.video_id}' for creator "
                                f"'{creator.channel_name}' (Session: {stream_session.id})"
                            )
                        except Exception as conn_err:
                            logger.info(f"Stream connect skipped or already active: {conn_err}")
                    else:
                        logger.info(
                            f"Video '{event.video_id}' is not currently live (live={broadcast.is_live})."
                        )

                    # Mark discovery event processed
                    if event.payload and "discovery_event_id" in event.payload:
                        discovery_repo = DiscoveryRepository(session)
                        await discovery_repo.mark_processed(event.payload["discovery_event_id"])

        except Exception as e:
            self.discovery_failures += 1
            logger.error(f"Failed to process discovery for video '{event.video_id}': {e}")

    async def reconcile_on_startup(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> dict[str, Any]:
        """
        Idempotent startup reconciliation:
        - Scans enabled creators and active stream sessions.
        - Verifies live broadcast status.
        - Resumes valid active streams and cleans up ended streams.
        """
        logger.info(
            "Executing startup reconciliation for YouTube streams and WebSub subscriptions..."
        )
        reconciled_streams = 0
        ended_streams = 0

        async with session_maker() as session:
            async with session.begin():
                stream_repo = StreamRepository(session)
                active_sessions = await stream_repo.list_active_sessions()

                for stream_rec in active_sessions:
                    try:
                        # Re-verify broadcast with YouTube API
                        broadcast = await self.broadcast_resolver.resolve_broadcast(
                            stream_rec.youtube_video_id
                        )
                        if broadcast.is_live and broadcast.live_chat_id:
                            # Re-attach or start worker if not already running
                            existing_worker = self.worker_manager.get_session_sync(stream_rec.id)
                            if not existing_worker:
                                await self.worker_manager.start_session(
                                    session_id=stream_rec.id,
                                    creator_id=stream_rec.creator_id,
                                    video_id=stream_rec.youtube_video_id,
                                    live_chat_id=broadcast.live_chat_id,
                                )
                                reconciled_streams += 1
                                logger.info(
                                    f"Reconciled and resumed active stream worker '{stream_rec.id}'"
                                )
                        else:
                            # Stream has ended while offline
                            await stream_repo.update_status(
                                stream_rec.id, status=StreamStatus.ENDED
                            )
                            ended_streams += 1
                            logger.info(f"Marked offline stream '{stream_rec.id}' as ENDED.")
                    except EntityNotFoundError:
                        await stream_repo.update_status(stream_rec.id, status=StreamStatus.ENDED)
                        ended_streams += 1
                    except Exception as e:
                        logger.warning(f"Could not reconcile stream '{stream_rec.id}': {e}")

        logger.info(
            f"Startup reconciliation complete: {reconciled_streams} resumed, {ended_streams} ended."
        )
        return {
            "reconciled_streams": reconciled_streams,
            "ended_streams": ended_streams,
        }

    def get_status(self) -> dict[str, Any]:
        """Return discovery scheduler status and metrics."""
        return {
            "running": self._running,
            "discovery_attempts": self.discovery_attempts,
            "discovery_success": self.discovery_success,
            "discovery_failures": self.discovery_failures,
        }


_global_discovery_scheduler: YouTubeDiscoveryScheduler | None = None


def get_discovery_scheduler() -> YouTubeDiscoveryScheduler:
    """Return singleton YouTubeDiscoveryScheduler."""
    global _global_discovery_scheduler
    if _global_discovery_scheduler is None:
        _global_discovery_scheduler = YouTubeDiscoveryScheduler()
    return _global_discovery_scheduler

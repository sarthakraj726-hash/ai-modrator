"""Monitored YouTube Channel Coordinator & Live Auto-Join Background Service."""

import asyncio
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import utc_now
from app.db.repositories.monitored_channel_repo import MonitoredChannelRepository
from app.db.repositories.stream_repo import StreamRepository
from app.services.stream_service import StreamService
from app.workers.manager import WorkerManager, get_worker_manager
from app.youtube.broadcast_resolver import YouTubeBroadcastResolver, get_broadcast_resolver
from app.youtube.url_resolver import YouTubeUrlResolver

logger = get_logger("app.services.monitored_channel_coordinator")


class MonitoredChannelCoordinator:
    """
    Periodic background coordinator for quota-conscious live detection
    and race-condition protected auto-joining of monitored YouTube channels.
    """

    def __init__(
        self,
        worker_manager: WorkerManager | None = None,
        broadcast_resolver: YouTubeBroadcastResolver | None = None,
        check_interval_seconds: float = 60.0,
    ) -> None:
        self.worker_manager = worker_manager or get_worker_manager()
        self.broadcast_resolver = broadcast_resolver or get_broadcast_resolver()
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Telemetry
        self.total_checks: int = 0
        self.live_detections: int = 0
        self.auto_joins: int = 0
        self.check_failures: int = 0

    async def start(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """Start the periodic coordinator background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(session_maker))
        logger.info(
            f"MonitoredChannelCoordinator started (interval: {self.check_interval_seconds}s)."
        )

    async def stop(self) -> None:
        """Stop the background coordinator gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("MonitoredChannelCoordinator stopped.")

    async def _run_loop(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """Periodic background evaluation loop."""
        while self._running:
            try:
                await self.check_all_active_channels(session_maker)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in MonitoredChannelCoordinator loop cycle: {e}")

            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def check_all_active_channels(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> dict[str, Any]:
        """Query and evaluate all active monitored channels."""
        channels_evaluated = 0
        streams_joined = 0

        async with session_maker() as session:
            mon_repo = MonitoredChannelRepository(session)
            active_channels = await mon_repo.list_all_active()

        for channel in active_channels:
            channels_evaluated += 1
            res = await self.check_channel(channel.id, session_maker)
            if res.get("auto_joined"):
                streams_joined += 1

        return {
            "channels_evaluated": channels_evaluated,
            "streams_joined": streams_joined,
        }

    async def check_channel(
        self,
        channel_record_id: str,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> dict[str, Any]:
        """
        Check a single channel for live broadcast status using quota-conscious detection
        and bootstrap the worker if live.
        """
        self.total_checks += 1
        redis = await get_redis_client()

        async with session_maker() as session:
            mon_repo = MonitoredChannelRepository(session)
            channel = await mon_repo.get_by_id(channel_record_id)
            if not channel or not channel.enabled:
                return {"status": "SKIPPED", "reason": "Channel not found or disabled"}

            channel_id = channel.youtube_channel_id
            creator_id = channel.creator_id
            auto_join_enabled = channel.auto_join_enabled

        lock_key = f"lock:monitored_channel:check:{channel_id}"
        lock_acquired = await redis.set(lock_key, "1", ex=45, nx=True)
        if not lock_acquired:
            return {"status": "SKIPPED", "reason": "Check already in progress on another worker"}

        try:
            # 1. Check if there is already an active session for this channel's known video
            async with session_maker() as session:
                async with session.begin():
                    stream_repo = StreamRepository(session)
                    active_sessions = await stream_repo.list_active()
                    for s in active_sessions:
                        if s.creator_id == creator_id and self.worker_manager.get_session_sync(s.id):
                            # Already active
                            mon_repo = MonitoredChannelRepository(session)
                            await mon_repo.update_check_status(
                                channel_id=channel_record_id,
                                is_live=True,
                                video_id=s.youtube_video_id,
                                stream_session_id=s.id,
                            )
                            return {
                                "status": "ALREADY_ACTIVE",
                                "video_id": s.youtube_video_id,
                                "stream_session_id": s.id,
                            }

            # 2. Quota-conscious probe: check YouTube /live redirect
            detected_video_id = await self._probe_live_video_id(channel_id)
            if not detected_video_id:
                async with session_maker() as session:
                    async with session.begin():
                        mon_repo = MonitoredChannelRepository(session)
                        await mon_repo.update_check_status(
                            channel_id=channel_record_id,
                            last_checked_at=utc_now(),
                            is_live=False,
                        )
                return {"status": "OFFLINE", "channel_id": channel_id}

            self.live_detections += 1
            logger.info(
                f"Live broadcast candidate detected for monitored channel '{channel_id}': video '{detected_video_id}'"
            )

            # 3. If auto_join is enabled, execute canonical stream bootstrap
            if auto_join_enabled:
                async with session_maker() as session:
                    async with session.begin():
                        stream_service = StreamService(
                            session=session,
                            worker_manager=self.worker_manager,
                            broadcast_resolver=self.broadcast_resolver,
                        )
                        try:
                            stream_session = await stream_service.canonical_bootstrap_stream(
                                url_or_video_id=detected_video_id,
                                creator_id=creator_id,
                                actor_id="AUTO_JOIN_COORDINATOR",
                                auto_join=True,
                            )
                            self.auto_joins += 1

                            mon_repo = MonitoredChannelRepository(session)
                            await mon_repo.update_check_status(
                                channel_id=channel_record_id,
                                is_live=True,
                                video_id=detected_video_id,
                                stream_session_id=stream_session.id,
                            )
                            return {
                                "status": "LIVE_AUTO_JOINED",
                                "auto_joined": True,
                                "video_id": detected_video_id,
                                "stream_session_id": stream_session.id,
                            }
                        except Exception as e:
                            self.check_failures += 1
                            safe_err = str(e)
                            err_code = getattr(e, "error_code", "AUTO_JOIN_FAILED")
                            if hasattr(e, "details") and isinstance(e.details, dict):
                                err_code = e.details.get("error_code", err_code)

                            mon_repo = MonitoredChannelRepository(session)
                            await mon_repo.update_check_status(
                                channel_id=channel_record_id,
                                is_live=False,
                                error_code=err_code,
                                error_message_safe=safe_err[:255],
                            )
                            logger.warning(
                                f"Failed to auto-join stream '{detected_video_id}' for channel '{channel_id}': {e}"
                            )
                            return {
                                "status": "AUTO_JOIN_FAILED",
                                "error_code": err_code,
                                "error": safe_err,
                            }
            else:
                async with session_maker() as session:
                    async with session.begin():
                        mon_repo = MonitoredChannelRepository(session)
                        await mon_repo.update_check_status(
                            channel_id=channel_record_id,
                            is_live=True,
                            video_id=detected_video_id,
                        )
                return {
                    "status": "LIVE_AUTO_JOIN_DISABLED",
                    "video_id": detected_video_id,
                }

        except Exception as e:
            self.check_failures += 1
            logger.error(f"Error checking monitored channel '{channel_record_id}': {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            await redis.delete(lock_key)

    async def _probe_live_video_id(self, youtube_channel_id: str) -> str | None:
        """
        Probe YouTube channel /live URL to detect active broadcast video ID
        without consuming YouTube Data API quota.
        """
        settings = get_settings()
        if settings.is_testing:
            # During test suite execution, probe resolves safely without outbound HTTP
            return None

        url = f"https://www.youtube.com/channel/{youtube_channel_id}/live"
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=4.0,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    final_url = str(resp.url)
                    if "watch?v=" in final_url:
                        res = YouTubeUrlResolver.resolve_video_id(final_url)
                        return res.video_id
                    # Inspect canonical link in HTML
                    import re

                    match = re.search(r'link rel="canonical" href="https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"', resp.text)
                    if match:
                        return match.group(1)
        except Exception as e:
            logger.debug(f"Live probe for {youtube_channel_id} encountered non-critical error: {e}")

        return None

    def get_status(self) -> dict[str, Any]:
        """Return coordinator telemetry and status snapshot."""
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "total_checks": self.total_checks,
            "live_detections": self.live_detections,
            "auto_joins": self.auto_joins,
            "check_failures": self.check_failures,
        }


_global_monitored_coordinator: MonitoredChannelCoordinator | None = None


def get_monitored_channel_coordinator() -> MonitoredChannelCoordinator:
    """Return the singleton MonitoredChannelCoordinator instance."""
    global _global_monitored_coordinator
    if _global_monitored_coordinator is None:
        _global_monitored_coordinator = MonitoredChannelCoordinator()
    return _global_monitored_coordinator

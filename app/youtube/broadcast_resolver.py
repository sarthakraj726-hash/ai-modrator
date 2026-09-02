"""Authoritative YouTube Broadcast and live status resolver."""

from datetime import UTC, datetime

from app.core.exceptions import EntityNotFoundError
from app.core.logging import get_logger
from app.youtube.client import YouTubeClient, get_youtube_client
from app.youtube.coalescer import global_coalescer
from app.youtube.models import ResolvedBroadcast

logger = get_logger("app.youtube.broadcast_resolver")


class YouTubeBroadcastResolver:
    """
    Authoritatively resolves YouTube video and broadcast metadata using minimal videos.list calls.
    Protects quota by coalescing concurrent in-flight calls and avoiding search.list.
    """

    def __init__(self, youtube_client: YouTubeClient | None = None) -> None:
        self.youtube_client = youtube_client or get_youtube_client()

    async def resolve_broadcast(self, video_id: str) -> ResolvedBroadcast:
        """
        Fetch broadcast metadata for a given video ID using single-flight request coalescing.
        """
        coalesce_key = f"broadcast:{video_id}"
        return await global_coalescer.execute(
            coalesce_key,
            lambda: self._fetch_broadcast_authoritative(video_id),
        )

    async def _fetch_broadcast_authoritative(self, video_id: str) -> ResolvedBroadcast:
        """Perform minimal videos.list call and map to ResolvedBroadcast."""
        data = await self.youtube_client.get_video_details(video_id)
        items = data.get("items", [])
        if not items:
            logger.warning(f"Video '{video_id}' not found in YouTube Data API.")
            raise EntityNotFoundError("YouTubeVideo", video_id)

        item = items[0]
        snippet = item.get("snippet", {})
        live_details = item.get("liveStreamingDetails", {})

        channel_id = snippet.get("channelId", "")
        channel_title = snippet.get("channelTitle", "")
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        live_broadcast_content = snippet.get("liveBroadcastContent", "none")

        active_chat_id = live_details.get("activeLiveChatId")
        actual_start_str = live_details.get("actualStartTime")
        scheduled_start_str = live_details.get("scheduledStartTime")
        concurrent_viewers_str = live_details.get("concurrentViewers")

        actual_start: datetime | None = None
        if actual_start_str:
            try:
                actual_start = datetime.fromisoformat(actual_start_str.replace("Z", "+00:00"))
            except Exception:
                pass

        scheduled_start: datetime | None = None
        if scheduled_start_str:
            try:
                scheduled_start = datetime.fromisoformat(scheduled_start_str.replace("Z", "+00:00"))
            except Exception:
                pass

        concurrent_viewers = (
            int(concurrent_viewers_str)
            if concurrent_viewers_str and concurrent_viewers_str.isdigit()
            else None
        )

        is_live = live_broadcast_content == "live" or (
            actual_start is not None and active_chat_id is not None
        )
        is_upcoming = live_broadcast_content == "upcoming"
        is_completed = live_broadcast_content == "completed" or (
            actual_start is not None and not is_live
        )

        logger.info(
            f"Resolved broadcast '{video_id}': title='{title[:30]}...', channel='{channel_id}', "
            f"live={is_live}, chat_id='{active_chat_id}'"
        )

        return ResolvedBroadcast(
            video_id=video_id,
            channel_id=channel_id,
            channel_title=channel_title,
            title=title,
            description=description,
            live_chat_id=active_chat_id,
            is_live=is_live,
            is_upcoming=is_upcoming,
            is_completed=is_completed,
            scheduled_start_time=scheduled_start,
            actual_start_time=actual_start,
            concurrent_viewers=concurrent_viewers,
            resolved_at=datetime.now(UTC),
        )


_global_broadcast_resolver: YouTubeBroadcastResolver | None = None


def get_broadcast_resolver() -> YouTubeBroadcastResolver:
    """Return the singleton YouTubeBroadcastResolver."""
    global _global_broadcast_resolver
    if _global_broadcast_resolver is None:
        _global_broadcast_resolver = YouTubeBroadcastResolver()
    return _global_broadcast_resolver

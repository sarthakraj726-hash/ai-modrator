"""Resilient YouTube Data API client interfacing through QuotaManager and ApiKeyPool."""

from typing import Any

import httpx

from app.core.exceptions import YouTubeAPIError
from app.core.logging import get_logger
from app.utils.circuit_breaker import CircuitBreaker
from app.utils.retry import retry_with_backoff
from app.youtube.key_pool import ApiKeyPool, get_key_pool
from app.youtube.models import (
    QuotaCost,
    YouTubeAuthor,
    YouTubeChatMessage,
    YouTubeChatPage,
    YouTubeStreamInfo,
)
from app.youtube.quota import QuotaManager, get_quota_manager

logger = get_logger("app.youtube.client")

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeClient:
    """
    YouTube API client strictly routed through QuotaManager and ApiKeyPool.
    Includes circuit breaker protection and exponential backoff retry.
    """

    def __init__(
        self,
        quota_manager: QuotaManager | None = None,
        key_pool: ApiKeyPool | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.quota_manager = quota_manager or get_quota_manager()
        self.key_pool = key_pool or get_key_pool()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            name="youtube-api",
            failure_threshold=5,
            recovery_timeout_seconds=30.0,
        )

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        quota_cost: int,
        method: str = "GET",
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute YouTube API HTTP request through QuotaManager, KeyPool, and CircuitBreaker.
        """
        # 1. Two-phase quota reservation
        reservation_id = await self.quota_manager.reserve(units=quota_cost)

        try:
            # 2. Key pool selection
            api_key = await self.key_pool.get_available_key()
            params_with_key = {**params, "key": api_key}

            url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"

            async def _do_http() -> dict[str, Any]:
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    if method == "GET":
                        response = await http_client.get(url, params=params_with_key)
                    else:
                        response = await http_client.request(
                            method, url, params=params_with_key, json=json_data
                        )

                    if response.status_code != 200:
                        error_msg = response.text
                        try:
                            err_json = response.json()
                            error_msg = err_json.get("error", {}).get("message", error_msg)
                        except Exception:
                            pass

                        await self.key_pool.record_error(
                            key=api_key,
                            status_code=response.status_code,
                            error_message=error_msg,
                        )
                        raise YouTubeAPIError(
                            message=f"YouTube API error ({response.status_code}): {error_msg}",
                            status_code=response.status_code,
                            details={"endpoint": endpoint, "params": params},
                        )

                    await self.key_pool.record_success(api_key)
                    await self.key_pool.record_usage(api_key, quota_cost)
                    return response.json()

            # 3. Execute through Circuit Breaker and Retries
            result = await self.circuit_breaker.execute(
                retry_with_backoff,
                _do_http,
                max_retries=2,
                base_delay=0.5,
            )

            # 4. Confirm quota consumption
            await self.quota_manager.consume(reservation_id)
            return result

        except Exception:
            # Release quota if failed prior to network or aborted
            await self.quota_manager.release_if_failed_before_request(reservation_id)
            raise

    async def resolve_stream_info(self, video_id: str) -> YouTubeStreamInfo:
        """Fetch broadcast metadata and live chat ID for a video."""
        params = {
            "part": "snippet,liveStreamingDetails",
            "id": video_id,
        }
        data = await self._request("videos", params=params, quota_cost=QuotaCost.VIDEOS_LIST)
        items = data.get("items", [])
        if not items:
            raise YouTubeAPIError(f"Video {video_id} not found on YouTube", status_code=404)

        item = items[0]
        snippet = item.get("snippet", {})
        live_details = item.get("liveStreamingDetails", {})

        return YouTubeStreamInfo(
            video_id=video_id,
            channel_id=snippet.get("channelId", ""),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            live_chat_id=live_details.get("activeLiveChatId"),
            is_live="actualStartTime" in live_details and "actualEndTime" not in live_details,
            concurrent_viewers=int(live_details.get("concurrentViewers", 0)) if "concurrentViewers" in live_details else None,
        )

    async def get_live_chat_messages(
        self,
        live_chat_id: str,
        page_token: str | None = None,
    ) -> YouTubeChatPage:
        """Poll live chat messages for a specific active chat."""
        params: dict[str, Any] = {
            "liveChatId": live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": 200,
        }
        if page_token:
            params["pageToken"] = page_token

        data = await self._request("liveChat/messages", params=params, quota_cost=QuotaCost.LIVE_CHAT_LIST)

        messages: list[YouTubeChatMessage] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            author_details = item.get("authorDetails", {})

            author = YouTubeAuthor(
                channel_id=author_details.get("channelId", ""),
                channel_url=author_details.get("channelUrl", ""),
                display_name=author_details.get("displayName", "Unknown"),
                profile_image_url=author_details.get("profileImageUrl", ""),
                is_chat_owner=author_details.get("isChatOwner", False),
                is_chat_sponsor=author_details.get("isChatSponsor", False),
                is_chat_moderator=author_details.get("isChatModerator", False),
                is_verified=author_details.get("isVerified", False),
            )

            msg = YouTubeChatMessage(
                message_id=item.get("id", ""),
                live_chat_id=live_chat_id,
                author=author,
                display_message=snippet.get("displayMessage", ""),
                message_type=snippet.get("type", "textMessageEvent"),
                raw_payload=item,
            )
            messages.append(msg)

        return YouTubeChatPage(
            messages=messages,
            next_page_token=data.get("nextPageToken"),
            polling_interval_millis=data.get("pollingIntervalMillis", 4000),
            offline_at=None,
        )


_global_youtube_client: YouTubeClient | None = None


def get_youtube_client() -> YouTubeClient:
    """Return singleton YouTubeClient instance."""
    global _global_youtube_client
    if _global_youtube_client is None:
        _global_youtube_client = YouTubeClient()
    return _global_youtube_client

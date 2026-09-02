"""Resilient YouTube Data API client interfacing through QuotaManager and ApiKeyPool."""

from typing import Any

import httpx

from app.core.exceptions import YouTubeAPIError
from app.core.logging import get_logger
from app.utils.circuit_breaker import CircuitBreaker
from app.utils.retry import retry_with_backoff
from app.youtube.key_pool import ApiKeyPool, get_key_pool
from app.youtube.models import (
    RequestClassification,
    YouTubeAuthor,
    YouTubeChatMessage,
    YouTubeChatPage,
    YouTubeStreamInfo,
)
from app.youtube.quota import QuotaManager, get_quota_manager
from app.youtube.quota_registry import quota_cost_registry

logger = get_logger("app.youtube.client")

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeClient:
    """
    YouTube API client strictly routed through QuotaManager and ApiKeyPool.
    Includes circuit breaker protection, per-method quota cost calculation, and retry backoff.
    """

    def __init__(
        self,
        quota_manager: QuotaManager | None = None,
        key_pool: ApiKeyPool | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
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
        method_name: str = "videos.list",
        quota_cost: int | None = None,
        http_method: str = "GET",
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute YouTube API HTTP request through QuotaManager, KeyPool, and CircuitBreaker.
        """
        cost = quota_cost if quota_cost is not None else quota_cost_registry.get_cost(method_name)

        # 1. Two-phase quota reservation
        reservation_id = await self.quota_manager.reserve(units=cost, method=method_name)

        try:
            # 2. Key pool selection
            api_key = await self.key_pool.get_available_key()
            params_with_key = {**params, "key": api_key}
            url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"

            from app.core.config import get_settings

            app_settings = get_settings()
            http_timeout = 0.5 if app_settings.is_testing else 10.0
            retry_delay = 0.01 if app_settings.is_testing else 0.5

            async def _do_http() -> dict[str, Any]:
                async with httpx.AsyncClient(timeout=http_timeout) as http_client:
                    if http_method == "GET":
                        response = await http_client.get(url, params=params_with_key)
                    else:
                        response = await http_client.request(
                            http_method, url, params=params_with_key, json=json_data
                        )

                    if response.status_code != 200:
                        error_msg = response.text
                        reason = "unknown"
                        try:
                            err_json = response.json()
                            error_obj = err_json.get("error", {})
                            error_msg = error_obj.get("message", error_msg)
                            errors = error_obj.get("errors", [])
                            if errors:
                                reason = errors[0].get("reason", "unknown")
                        except Exception:
                            pass

                        await self.key_pool.record_error(
                            key=api_key,
                            status_code=response.status_code,
                            error_message=f"{reason}: {error_msg}",
                        )

                        # Classify failure
                        classification = RequestClassification.HTTP_500
                        if response.status_code == 400:
                            classification = RequestClassification.HTTP_400
                        elif response.status_code == 401:
                            classification = RequestClassification.HTTP_401
                        elif response.status_code == 403:
                            classification = RequestClassification.HTTP_403
                        elif response.status_code == 404:
                            classification = RequestClassification.HTTP_404
                        elif response.status_code == 409:
                            classification = RequestClassification.HTTP_409
                        elif response.status_code == 429:
                            classification = RequestClassification.HTTP_429
                        elif response.status_code == 502:
                            classification = RequestClassification.HTTP_502
                        elif response.status_code == 503:
                            classification = RequestClassification.HTTP_503
                        elif response.status_code == 504:
                            classification = RequestClassification.HTTP_504

                        raise YouTubeAPIError(
                            message=f"YouTube API error ({response.status_code} {reason}): {error_msg}",
                            status_code=response.status_code,
                            reason=reason,
                            details={
                                "endpoint": endpoint,
                                "params": params,
                                "classification": classification.value,
                            },
                        )

                    await self.key_pool.record_success(api_key)
                    await self.key_pool.record_usage(api_key, cost)
                    return response.json()

            # 3. Execute through Circuit Breaker and Retries
            result = await self.circuit_breaker.execute(
                retry_with_backoff,
                _do_http,
                max_retries=2,
                base_delay=retry_delay,
            )

            # 4. Confirm quota consumption
            await self.quota_manager.consume(reservation_id, method=method_name)
            return result

        except Exception as e:
            # Conservative quota accounting
            if isinstance(e, YouTubeAPIError):
                await self.quota_manager.record_failure(
                    reservation_id,
                    classification=RequestClassification.REQUEST_SENT_NETWORK_FAILURE,
                    method=method_name,
                )
            else:
                await self.quota_manager.release_if_not_dispatched(reservation_id)
            raise

    async def get_video_details(self, video_id: str) -> dict[str, Any]:
        """Fetch video metadata using videos.list (1 unit)."""
        params = {
            "part": "snippet,liveStreamingDetails",
            "id": video_id,
        }
        return await self._request("videos", params=params, method_name="videos.list")

    async def get_channel_details(self, channel_id: str) -> dict[str, Any]:
        """Fetch channel metadata using channels.list (1 unit)."""
        params = {
            "part": "snippet,contentDetails",
            "id": channel_id,
        }
        return await self._request("channels", params=params, method_name="channels.list")

    async def get_channel_by_handle(self, handle: str) -> dict[str, Any]:
        """Fetch channel by handle using channels.list (1 unit)."""
        params = {
            "part": "snippet,contentDetails",
            "forHandle": handle if handle.startswith("@") else f"@{handle}",
        }
        return await self._request("channels", params=params, method_name="channels.list")

    async def resolve_stream_info(self, video_id: str) -> YouTubeStreamInfo:
        """Fetch broadcast metadata and live chat ID for a video."""
        data = await self.get_video_details(video_id)
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
            concurrent_viewers=int(live_details.get("concurrentViewers", 0))
            if "concurrentViewers" in live_details
            else None,
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

        data = await self._request(
            "liveChat/messages", params=params, method_name="liveChatMessages.list"
        )

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

        offline_at = None
        offline_at_str = data.get("offlineAt")
        if offline_at_str:
            try:
                from datetime import datetime

                offline_at = datetime.fromisoformat(offline_at_str.replace("Z", "+00:00"))
            except Exception:
                pass

        return YouTubeChatPage(
            messages=messages,
            next_page_token=data.get("nextPageToken"),
            polling_interval_millis=data.get("pollingIntervalMillis", 4000),
            offline_at=offline_at,
        )


_global_youtube_client: YouTubeClient | None = None


def get_youtube_client() -> YouTubeClient:
    """Return singleton YouTubeClient instance."""
    global _global_youtube_client
    if _global_youtube_client is None:
        _global_youtube_client = YouTubeClient()
    return _global_youtube_client

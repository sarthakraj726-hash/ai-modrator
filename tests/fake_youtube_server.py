"""Deterministic Fake YouTube API Server for contract, integration, and chaos testing."""

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


class FakeYouTubeServer:
    """
    Deterministic mock HTTP transport for YouTube Data API v3.
    Simulates videos.list, channels.list, and liveChatMessages.list/streamList endpoints,
    along with comprehensive error injection controls.
    """

    def __init__(self) -> None:
        self.status_overrides: dict[str, int] = {}
        self.error_reasons: dict[str, str] = {}
        self.video_database: dict[str, dict[str, Any]] = {}
        self.channel_database: dict[str, dict[str, Any]] = {}
        self.chat_messages_database: dict[str, list[dict[str, Any]]] = {}
        self.chat_offline_database: dict[str, bool] = {}
        self.polling_intervals: dict[str, int] = {}
        self.request_history: list[dict[str, Any]] = []

        # Seed default mock data
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Seed initial mock videos and channels."""
        self.video_database["test_live_video_1"] = {
            "id": "test_live_video_1",
            "snippet": {
                "channelId": "UC_TEST_CHANNEL_1",
                "channelTitle": "Goddess Streamer 1",
                "title": "Epic Live Stream #1",
                "description": "Playing games live!",
                "liveBroadcastContent": "live",
            },
            "liveStreamingDetails": {
                "activeLiveChatId": "chat_live_id_1",
                "actualStartTime": "2026-09-02T10:00:00Z",
                "concurrentViewers": "1500",
            },
        }

        self.channel_database["UC_TEST_CHANNEL_1"] = {
            "id": "UC_TEST_CHANNEL_1",
            "snippet": {
                "title": "Goddess Streamer 1",
                "customUrl": "@goddess1",
            },
        }

        self.chat_messages_database["chat_live_id_1"] = [
            {
                "id": "msg_001",
                "snippet": {
                    "type": "textMessageEvent",
                    "displayMessage": "Hello stream!",
                },
                "authorDetails": {
                    "channelId": "UC_VIEWER_1",
                    "displayName": "Viewer One",
                    "isChatOwner": False,
                    "isChatModerator": False,
                    "isChatSponsor": False,
                    "isVerified": False,
                },
            },
            {
                "id": "msg_002",
                "snippet": {
                    "type": "textMessageEvent",
                    "displayMessage": "Mod message here",
                },
                "authorDetails": {
                    "channelId": "UC_MOD_1",
                    "displayName": "Mod One",
                    "isChatOwner": False,
                    "isChatModerator": True,
                    "isChatSponsor": True,
                    "isVerified": True,
                },
            },
        ]

    def register_video(
        self,
        video_id: str,
        channel_id: str,
        live_chat_id: str | None = None,
        is_live: bool = True,
        title: str = "Test Video",
    ) -> None:
        """Register custom test video."""
        self.video_database[video_id] = {
            "id": video_id,
            "snippet": {
                "channelId": channel_id,
                "channelTitle": f"Creator {channel_id}",
                "title": title,
                "description": "Test description",
                "liveBroadcastContent": "live" if is_live else "none",
            },
            "liveStreamingDetails": {
                "activeLiveChatId": live_chat_id,
                "actualStartTime": "2026-09-02T10:00:00Z" if is_live else None,
                "concurrentViewers": "100",
            }
            if is_live and live_chat_id
            else {},
        }

    def register_chat_messages(self, live_chat_id: str, messages: list[dict[str, Any]]) -> None:
        """Register mock chat messages for a chat ID."""
        self.chat_messages_database[live_chat_id] = messages

    def set_offline(self, live_chat_id: str, is_offline: bool = True) -> None:
        """Mark a live chat as offline."""
        self.chat_offline_database[live_chat_id] = is_offline

    def set_status_override(self, endpoint: str, status_code: int, reason: str = "error") -> None:
        """Inject HTTP error code for endpoint (e.g., 'videos', 'liveChat/messages')."""
        self.status_overrides[endpoint] = status_code
        self.error_reasons[endpoint] = reason

    def clear_status_override(self, endpoint: str) -> None:
        """Clear error override for endpoint."""
        self.status_overrides.pop(endpoint, None)
        self.error_reasons.pop(endpoint, None)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """HTTPX mock transport request handler."""
        parsed = urlparse(str(request.url))
        endpoint = parsed.path.replace("/youtube/v3/", "")
        query_params = parse_qs(parsed.query)

        self.request_history.append(
            {
                "method": request.method,
                "url": str(request.url),
                "endpoint": endpoint,
                "params": query_params,
            }
        )

        # Check for status override / fault injection
        if endpoint in self.status_overrides:
            status_code = self.status_overrides[endpoint]
            reason = self.error_reasons.get(endpoint, "injected_error")
            return httpx.Response(
                status_code,
                json={
                    "error": {
                        "code": status_code,
                        "message": f"Injected error for {endpoint}",
                        "errors": [{"reason": reason, "message": f"Injected failure ({reason})"}],
                    }
                },
            )

        # 1. /videos endpoint
        if endpoint == "videos":
            video_ids = query_params.get("id", [""])[0].split(",")
            items = []
            for vid in video_ids:
                if vid in self.video_database:
                    items.append(self.video_database[vid])
            return httpx.Response(200, json={"kind": "youtube#videoListResponse", "items": items})

        # 2. /channels endpoint
        if endpoint == "channels":
            channel_ids = query_params.get("id", [""])[0].split(",")
            items = []
            for cid in channel_ids:
                if cid in self.channel_database:
                    items.append(self.channel_database[cid])
            return httpx.Response(200, json={"kind": "youtube#channelListResponse", "items": items})

        # 3. /liveChat/messages endpoint
        if endpoint == "liveChat/messages":
            if request.method == "POST":
                import json

                try:
                    body = json.loads(request.content.decode("utf-8")) if request.content else {}
                except Exception:
                    body = {}
                snippet = body.get("snippet", {})
                chat_id = snippet.get("liveChatId") or query_params.get("liveChatId", [""])[0]
                text_details = snippet.get("textMessageDetails", {})
                msg_text = text_details.get("messageText", "")

                new_msg = {
                    "kind": "youtube#liveChatMessage",
                    "id": f"msg_mock_{len(self.request_history)}",
                    "snippet": {
                        "liveChatId": chat_id,
                        "type": snippet.get("type", "textMessageEvent"),
                        "displayMessage": msg_text,
                        "publishedAt": "2026-09-05T12:00:00Z",
                    },
                    "authorDetails": {
                        "channelId": "UC_BOT_CHANNEL",
                        "displayName": "Goddess AI",
                        "isChatModerator": True,
                    },
                }
                if chat_id in self.chat_messages_database:
                    self.chat_messages_database[chat_id].append(new_msg)
                return httpx.Response(200, json=new_msg)

            if request.method == "DELETE":
                return httpx.Response(204)

            chat_id = query_params.get("liveChatId", [""])[0]
            is_offline = self.chat_offline_database.get(chat_id, False)
            messages = self.chat_messages_database.get(chat_id, [])
            page_token = query_params.get("pageToken", [""])[0]

            polling_interval = self.polling_intervals.get(chat_id, 50)  # Fast 50ms for tests

            resp_payload: dict[str, Any] = {
                "kind": "youtube#liveChatMessageListResponse",
                "items": messages if not page_token else [],
                "nextPageToken": f"token_next_{chat_id}_2"
                if not page_token
                else f"token_next_{chat_id}_3",
                "pollingIntervalMillis": polling_interval,
            }
            if is_offline:
                resp_payload["offlineAt"] = "2026-09-02T12:00:00Z"

            return httpx.Response(200, json=resp_payload)

        # Default fallback 404
        return httpx.Response(
            404, json={"error": {"code": 404, "message": f"Unknown endpoint '{endpoint}'"}}
        )

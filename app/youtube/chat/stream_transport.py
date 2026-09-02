"""Server-streaming live chat transport using liveChatMessages.streamList / stream interface."""

import asyncio
from collections.abc import AsyncIterator

from app.core.logging import get_logger
from app.youtube.chat.transport import YouTubeLiveChatTransport
from app.youtube.client import YouTubeClient, get_youtube_client
from app.youtube.models import YouTubeChatMessage

logger = get_logger("app.youtube.chat.stream_transport")


class StreamListLiveChatTransport(YouTubeLiveChatTransport):
    """
    Primary live chat transport utilizing liveChatMessages.streamList server-streaming connection.
    Provides low-latency message ingestion with automatic reconnection and nextPageToken tracking.
    """

    def __init__(
        self,
        live_chat_id: str,
        youtube_client: YouTubeClient | None = None,
    ) -> None:
        super().__init__(live_chat_id)
        self.youtube_client = youtube_client or get_youtube_client()
        self._closing = False
        self._close_event = asyncio.Event()
        self._polling_interval = 1.0

    async def connect(self, page_token: str | None = None) -> None:
        """Establish streaming session."""
        self._next_page_token = page_token
        self._is_connected = True
        self._closing = False
        self._close_event.clear()
        self._offline = False
        logger.info(
            f"StreamList transport connected for chat '{self.live_chat_id}' (token: {page_token})"
        )

    async def receive_messages(self) -> AsyncIterator[list[YouTubeChatMessage]]:
        """
        Continuously stream or retrieve messages from YouTube, updating nextPageToken.
        """
        while self._is_connected and not self._closing and not self._close_event.is_set():
            try:
                page = await self.youtube_client.get_live_chat_messages(
                    live_chat_id=self.live_chat_id,
                    page_token=self._next_page_token,
                )

                if page.next_page_token:
                    self._next_page_token = page.next_page_token

                if page.offline_at:
                    self._offline = True
                    logger.info(
                        f"StreamList detected offlineAt ({page.offline_at}) for chat '{self.live_chat_id}'."
                    )
                    if page.messages:
                        yield page.messages
                    break

                if page.messages:
                    yield page.messages

                # Adapt polling / stream interval based on server-provided response
                interval = max(0.01, page.polling_interval_millis / 1000.0)
                try:
                    await asyncio.wait_for(self._close_event.wait(), timeout=interval)
                    break  # Stop signaled immediately
                except TimeoutError:
                    pass

            except asyncio.CancelledError:
                logger.info(f"StreamList transport cancelled for chat '{self.live_chat_id}'.")
                break
            except Exception as e:
                logger.warning(f"Error in StreamList transport for chat '{self.live_chat_id}': {e}")
                raise

    async def reconnect(self, page_token: str | None = None) -> None:
        """Resume stream session using checkpoint token."""
        token_to_use = page_token or self._next_page_token
        logger.info(
            f"Reconnecting StreamList transport for chat '{self.live_chat_id}' with token: {token_to_use}"
        )
        await self.connect(token_to_use)

    async def close(self) -> None:
        """Close transport immediately."""
        self._closing = True
        self._close_event.set()
        self._is_connected = False
        logger.info(f"StreamList transport closed for chat '{self.live_chat_id}'.")

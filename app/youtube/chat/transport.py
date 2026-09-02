"""Abstract interface for YouTube Live Chat transports."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.youtube.models import YouTubeChatMessage


class YouTubeLiveChatTransport(ABC):
    """Abstract base class for live chat ingestion transports (streaming or polling)."""

    def __init__(self, live_chat_id: str) -> None:
        self.live_chat_id = live_chat_id
        self._next_page_token: str | None = None
        self._is_connected: bool = False
        self._offline: bool = False

    @property
    def next_page_token(self) -> str | None:
        return self._next_page_token

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_offline(self) -> bool:
        return self._offline

    @abstractmethod
    async def connect(self, page_token: str | None = None) -> None:
        """Establish connection or initialize chat stream for liveChatId."""
        pass

    @abstractmethod
    async def receive_messages(self) -> AsyncIterator[list[YouTubeChatMessage]]:
        """Yield batches of incoming live chat messages."""
        pass

    @abstractmethod
    async def reconnect(self, page_token: str | None = None) -> None:
        """Reconnect or resume ingestion using the latest checkpoint page token."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully terminate transport connection."""
        pass

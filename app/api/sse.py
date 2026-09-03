"""Event-driven Server-Sent Events (SSE) broadcaster with bounded buffers and client lifecycle management."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.events.bus import EventBus, get_event_bus
from app.events.schemas import BaseEvent

logger = get_logger("app.api.sse")


class SSEBroadcaster:
    """
    Manages real-time SSE fanout to developer control center clients.
    Subscribes to the EventBus, formats events according to SSE specification,
    enforces bounded per-client buffers, and handles client disconnect cleanup.
    """

    def __init__(self, max_buffer_per_client: int = 100, heartbeat_interval: float = 15.0):
        self.max_buffer_per_client = max_buffer_per_client
        self.heartbeat_interval = heartbeat_interval
        self._clients: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._subscribed = False

    def setup_eventbus_subscription(self, event_bus: EventBus | None = None) -> None:
        """Subscribe this broadcaster to the application EventBus."""
        if self._subscribed:
            return
        bus = event_bus or get_event_bus()
        bus.subscribe_all(self._handle_event)
        self._subscribed = True
        logger.info("SSEBroadcaster subscribed to domain EventBus")

    async def _handle_event(self, event: BaseEvent) -> None:
        """Receive domain event and fan out to all active SSE client queues."""
        if not self._clients:
            return

        payload = {
            "id": event.event_id,
            "event": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "creator_id": event.creator_id,
            "stream_session_id": event.stream_session_id,
            "data": event.model_dump(mode="json"),
        }

        async with self._lock:
            client_ids = list(self._clients.keys())

        for cid in client_ids:
            q = self._clients.get(cid)
            if not q:
                continue
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Discard oldest message to prevent unbounded memory growth
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass

    async def register_client(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        """Register a new SSE client connection and return unique ID with bounded queue."""
        client_id = str(uuid.uuid4())
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self.max_buffer_per_client)
        async with self._lock:
            self._clients[client_id] = q
        logger.debug(f"Registered SSE client {client_id} (active: {len(self._clients)})")
        return client_id, q

    async def unregister_client(self, client_id: str) -> None:
        """Cleanly remove client queue upon connection termination."""
        async with self._lock:
            self._clients.pop(client_id, None)
        logger.debug(f"Unregistered SSE client {client_id} (active: {len(self._clients)})")

    def get_active_client_count(self) -> int:
        """Return count of currently connected SSE clients."""
        return len(self._clients)

    async def client_event_generator(
        self,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Yield SSE formatted messages to client until disconnected.
        Emits periodic heartbeats to detect connection drops.
        """
        self.setup_eventbus_subscription()
        client_id, queue = await self.register_client()

        # Send initial connection acknowledgment
        initial_msg = {
            "event": "connected",
            "id": str(uuid.uuid4()),
            "data": json.dumps(
                {
                    "client_id": client_id,
                    "connected_at": datetime.now(UTC).isoformat(),
                    "message": "Connected to Goddess AI SSE broadcast feed",
                }
            ),
        }
        yield f"id: {initial_msg['id']}\nevent: {initial_msg['event']}\ndata: {initial_msg['data']}\n\n"

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=self.heartbeat_interval)
                    event_type = msg.get("event", "message")
                    event_id = msg.get("id", str(uuid.uuid4()))
                    data_str = json.dumps(msg.get("data", {}))
                    yield f"id: {event_id}\nevent: {event_type}\ndata: {data_str}\n\n"
                except TimeoutError:
                    # Send keep-alive heartbeat comment
                    now_iso = datetime.now(UTC).isoformat()
                    yield f": heartbeat {now_iso}\n\n"
        except asyncio.CancelledError:
            logger.debug(f"SSE client {client_id} disconnected (cancelled)")
        finally:
            await self.unregister_client(client_id)


_global_broadcaster: SSEBroadcaster | None = None


def get_sse_broadcaster() -> SSEBroadcaster:
    """Return singleton SSEBroadcaster."""
    global _global_broadcaster
    if _global_broadcaster is None:
        _global_broadcaster = SSEBroadcaster()
    return _global_broadcaster

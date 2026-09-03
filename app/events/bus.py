"""Asynchronous event bus for domain events with in-memory and Redis pub/sub routing."""

import asyncio
import inspect
import json
import os
import uuid
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.events.schemas import BaseEvent

logger = get_logger("app.events.bus")

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Decoupled asynchronous event bus supporting multiple typed subscribers
    per event topic, with unified in-process and distributed Redis Pub/Sub support.
    """

    def __init__(self, channel_prefix: str = "goddess:events"):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._all_subscribers: list[EventHandler] = []
        self._lock = asyncio.Lock()
        self.channel_prefix = channel_prefix
        self.instance_id = f"proc-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._listener_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Telemetry metrics
        self.events_published: int = 0
        self.events_received_remote: int = 0
        self.last_published_at: datetime | None = None
        self.last_received_at: datetime | None = None
        self.last_listener_error: str | None = None
        self.consecutive_listener_failures: int = 0
        self.last_success_at: datetime | None = None
        self.last_failure_at: datetime | None = None

    def _extract_type_name(self, event_type: str | type[BaseEvent]) -> str:
        if isinstance(event_type, str):
            return event_type
        if hasattr(event_type, "model_fields") and "event_type" in event_type.model_fields:
            default_val = event_type.model_fields["event_type"].default
            if default_val is not None:
                return str(default_val)
        return event_type.__name__

    def subscribe(self, event_type: str | type[BaseEvent], handler: EventHandler) -> None:
        """Register a subscriber callback for a specific event type or event class."""
        type_name = self._extract_type_name(event_type)
        self._subscribers[type_name].append(handler)
        logger.debug(f"Subscribed handler '{handler.__name__}' to event '{type_name}'")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a subscriber callback that receives all emitted events."""
        self._all_subscribers.append(handler)

    def unsubscribe(self, event_type: str | type[BaseEvent], handler: EventHandler) -> bool:
        """Remove a subscriber callback."""
        type_name = event_type if isinstance(event_type, str) else event_type.__name__
        if handler in self._subscribers[type_name]:
            self._subscribers[type_name].remove(handler)
            return True
        return False

    async def publish(self, event: BaseEvent, broadcast_distributed: bool = True) -> None:
        """
        Publish an event to local subscribers and optionally broadcast to Redis Pub/Sub
        for decoupled multi-process deployments.
        """
        type_name = event.event_type
        self.events_published += 1
        self.last_published_at = datetime.now(UTC)

        # 1. Dispatch locally
        await self._dispatch_local(event)

        # 2. Dispatch to Redis pub/sub if enabled
        if broadcast_distributed:
            try:
                redis = await get_redis_client()
                if redis and not getattr(redis, "_is_fallback", False):
                    channel = f"{self.channel_prefix}:{type_name}"
                    envelope = {
                        "sender_instance_id": self.instance_id,
                        "event_type": type_name,
                        "payload": event.model_dump(mode="json"),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    await redis.publish(channel, json.dumps(envelope))
            except Exception as e:
                logger.debug(f"EventBus Redis pub/sub broadcast skipped/failed: {e}")

    async def _dispatch_local(self, event: BaseEvent) -> None:
        """Dispatch event to local in-process registered handlers."""
        type_name = event.event_type
        handlers = list(self._subscribers.get(type_name, [])) + list(self._all_subscribers)
        if not handlers:
            return

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.create_task(self._safe_execute(handler, event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Error invoking event handler '{handler.__name__}' for '{type_name}': {e}",
                    exc_info=True,
                )

    async def _safe_execute(self, handler: EventHandler, event: BaseEvent) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Async exception in event handler '{handler.__name__}' on event '{event.event_type}': {e}",
                exc_info=True,
            )

    async def start_distributed_listener(self) -> None:
        """Start background consumer task for Redis Pub/Sub events across processes."""
        if self._listener_task and not self._listener_task.done():
            return

        self._stop_event.clear()
        self._listener_task = asyncio.create_task(self._listen_redis_loop())
        logger.info(f"EventBus distributed listener started on instance {self.instance_id}")

    async def stop_distributed_listener(self) -> None:
        """Stop background Redis Pub/Sub listener."""
        self._stop_event.set()
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        logger.info("EventBus distributed listener stopped")

    async def _listen_redis_loop(self) -> None:
        """Background loop reading from Redis Pub/Sub channels."""
        while not self._stop_event.is_set():
            pubsub = None
            try:
                redis = await get_redis_client()
                if not redis or getattr(redis, "_is_fallback", False):
                    self.consecutive_listener_failures += 1
                    self.last_failure_at = datetime.now(UTC)
                    self.last_listener_error = "Redis transport unavailable or fallback active"
                    await asyncio.sleep(2.0)
                    continue

                pubsub = redis.pubsub()
                pattern = f"{self.channel_prefix}:*"
                await pubsub.psubscribe(pattern)

                # Successfully subscribed
                self.consecutive_listener_failures = 0
                self.last_success_at = datetime.now(UTC)
                self.last_listener_error = None

                while not self._stop_event.is_set():
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not message or message.get("type") != "pmessage":
                        await asyncio.sleep(0.05)
                        continue

                    raw_data = message.get("data")
                    if not raw_data:
                        continue

                    try:
                        envelope = (
                            json.loads(raw_data.decode("utf-8"))
                            if isinstance(raw_data, bytes)
                            else json.loads(raw_data)
                        )
                        sender_id = envelope.get("sender_instance_id")
                        if sender_id == self.instance_id:
                            continue  # Ignore self-emitted reflection

                        event_type = envelope.get("event_type")
                        payload = envelope.get("payload", {})
                        self.events_received_remote += 1
                        self.last_received_at = datetime.now(UTC)

                        # Reconstitute typed event and dispatch locally
                        from app.events.schemas import EVENT_TYPE_MAP

                        event_cls = EVENT_TYPE_MAP.get(event_type, BaseEvent)
                        event_instance = event_cls(**payload)
                        await self._dispatch_local(event_instance)
                    except Exception as parse_err:
                        logger.debug(f"Error handling distributed event: {parse_err}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.consecutive_listener_failures += 1
                self.last_failure_at = datetime.now(UTC)
                self.last_listener_error = str(e)
                logger.debug(f"EventBus distributed listener loop error: {e}")
                await asyncio.sleep(2.0)
            finally:
                if pubsub:
                    try:
                        await pubsub.close()
                    except Exception:
                        pass

    def get_health(self) -> dict[str, Any]:
        """Return structured EventBus health and diagnostic telemetry."""
        total_subscribers = sum(len(h) for h in self._subscribers.values()) + len(
            self._all_subscribers
        )
        settings = get_settings()
        is_unified = settings.is_unified_service
        mode = "UNIFIED" if is_unified else "DECOUPLED"

        listener_active = bool(self._listener_task and not self._listener_task.done())

        # In UNIFIED mode, EventBus is local in-memory dispatch and always operational
        if is_unified:
            status = "HEALTHY"
            transport_available = True
        else:
            # In DECOUPLED mode, check Redis transport availability and listener task state
            from app.cache.redis import get_redis_sync

            redis_cli = get_redis_sync()
            is_fallback = getattr(redis_cli, "_is_fallback", False)
            transport_available = not is_fallback

            if listener_active and transport_available and self.consecutive_listener_failures == 0:
                status = "HEALTHY"
            elif (
                not transport_available
                or not listener_active
                or self.consecutive_listener_failures > 3
            ):
                status = (
                    "UNHEALTHY"
                    if (not listener_active or self.consecutive_listener_failures > 5)
                    else "DEGRADED"
                )
            else:
                status = "DEGRADED"

        return {
            "status": status,
            "mode": mode,
            "instance_id": self.instance_id,
            "subscribers_registered": total_subscribers,
            "topics_count": len(self._subscribers),
            "events_published": self.events_published,
            "events_received_remote": self.events_received_remote,
            "listener_active": listener_active,
            "transport_available": transport_available,
            "last_published_at": self.last_published_at.isoformat()
            if self.last_published_at
            else None,
            "last_received_at": self.last_received_at.isoformat()
            if self.last_received_at
            else None,
            "last_listener_error": self.last_listener_error,
            "consecutive_listener_failures": self.consecutive_listener_failures,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
        }

    def clear(self) -> None:
        """Clear all registered event subscribers (used in test teardown)."""
        self._subscribers.clear()
        self._all_subscribers.clear()


_global_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the singleton application event bus."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus

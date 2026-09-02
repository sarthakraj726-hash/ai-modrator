"""Asynchronous event bus for domain events with in-memory and Redis pub/sub routing."""

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import get_logger
from app.events.schemas import BaseEvent

logger = get_logger("app.events.bus")

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Decoupled asynchronous event bus supporting multiple typed subscribers
    per event topic.
    """

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._all_subscribers: list[EventHandler] = []
        self._lock = asyncio.Lock()

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

    async def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all registered topic and wildcard subscribers.
        Dispatches asynchronously; handler exceptions are logged without disrupting
        other subscribers or the publisher.
        """
        type_name = event.event_type
        handlers = list(self._subscribers.get(type_name, [])) + list(self._all_subscribers)

        if not handlers:
            logger.debug(f"No subscribers registered for event '{type_name}'")
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

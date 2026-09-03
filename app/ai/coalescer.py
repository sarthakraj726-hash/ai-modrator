"""Single-flight request coalescing for concurrent AI tasks."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class AIRequestCoalescer:
    """
    Suppresses duplicate concurrent AI requests for the same message/task.
    If multiple workers request classification for the same (creator_id, stream_id, message_id, task),
    only one executes while the others await and receive the leader's result.
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()
        self.total_requests: int = 0
        self.coalesced_requests: int = 0

    def make_key(
        self, creator_id: str, stream_session_id: str, message_id: str, task_type: str
    ) -> str:
        """Compose coalescing key."""
        return f"ai:{creator_id}:{stream_session_id}:{message_id}:{task_type}"

    async def execute(self, key: str, action: Callable[[], Awaitable[T]]) -> T:
        """
        Execute action if no request is currently in-flight for key;
        otherwise wait for and return the result of the in-flight request.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] | None = None
        is_leader = False

        async with self._lock:
            self.total_requests += 1
            if key in self._in_flight:
                self.coalesced_requests += 1
                future = self._in_flight[key]
            else:
                future = loop.create_future()
                self._in_flight[key] = future
                is_leader = True

        if not is_leader:
            assert future is not None
            return await future

        try:
            result = await action()
            if not future.done():
                future.set_result(result)
            return result
        except BaseException as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(key, None)


_global_ai_coalescer: AIRequestCoalescer | None = None


def get_ai_coalescer() -> AIRequestCoalescer:
    """Return singleton AIRequestCoalescer."""
    global _global_ai_coalescer
    if _global_ai_coalescer is None:
        _global_ai_coalescer = AIRequestCoalescer()
    return _global_ai_coalescer

"""Single-flight request coalescing to prevent duplicate in-flight API calls."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class SingleFlightCoalescer:
    """
    Suppresses duplicate concurrent calls for the same key.
    If multiple tasks request resolution for the same key while one is in-flight,
    all callers await the same shared task rather than triggering duplicate network requests.
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()
        self.total_requests: int = 0
        self.coalesced_requests: int = 0

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
            # Follower: await leader's result
            assert future is not None
            return await future

        # Leader: execute action and notify all followers
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


# Global coalescer instance for YouTube resolvers
global_coalescer = SingleFlightCoalescer()

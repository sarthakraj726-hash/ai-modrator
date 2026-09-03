"""Circuit Breaker pattern implementation to prevent cascading remote failures."""

import asyncio
import time
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from app.core.exceptions import CircuitBreakerOpenError
from app.core.logging import get_logger

logger = get_logger("app.utils.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # Normal operation, requests pass through
    OPEN = "OPEN"  # Failing, fast-reject all requests
    HALF_OPEN = "HALF_OPEN"  # Testing canary requests after cooldown


class CircuitBreaker:
    """
    Asynchronous Circuit Breaker.
    Transitions:
      CLOSED -> (failure_count >= failure_threshold) -> OPEN
      OPEN -> (time > open_until) -> HALF_OPEN
      HALF_OPEN -> (success) -> CLOSED
      HALF_OPEN -> (failure) -> OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_attempts: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_attempts = half_open_max_attempts

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.consecutive_success_count = 0
        self.open_until = 0.0
        self._lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        """Return True if circuit is currently in OPEN state."""
        return self.state == CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Check if request is permitted under current circuit state."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now >= self.open_until:
                    logger.info(f"Circuit '{self.name}' transitioning from OPEN to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.consecutive_success_count = 0
                    return True
                return False
            return True

    async def record_success(self) -> None:
        """Record a successful operation and potentially close half-open circuit."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.consecutive_success_count += 1
                if self.consecutive_success_count >= self.half_open_max_attempts:
                    logger.info(
                        f"Circuit '{self.name}' recovered. Transitioning from HALF_OPEN to CLOSED."
                    )
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.consecutive_success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def record_failure(self, exception: Exception | None = None) -> None:
        """Record a failed operation and trip circuit if threshold reached."""
        async with self._lock:
            self.failure_count += 1
            now = time.time()
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.open_until = now + self.recovery_timeout_seconds
                logger.warning(
                    f"Circuit '{self.name}' TRIPPED to OPEN! Blocking calls for {self.recovery_timeout_seconds}s. "
                    f"Failures: {self.failure_count}. Last error: {exception}"
                )

    async def execute(
        self, coro_func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute a coroutine wrapped within the circuit breaker boundary."""
        if not await self.can_execute():
            remaining = max(0.0, self.open_until - time.time())
            raise CircuitBreakerOpenError(circuit_name=self.name, reset_time_seconds=remaining)

        try:
            result = await coro_func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as exc:
            await self.record_failure(exc)
            raise

    def reset(self) -> None:
        """Manually reset circuit breaker to clean CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.consecutive_success_count = 0
        self.open_until = 0.0

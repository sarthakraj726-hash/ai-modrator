"""Exponential backoff with full jitter for resilient remote operations."""

import asyncio
import random
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    YouTubeQuotaExceededError,
)
from app.core.logging import get_logger

logger = get_logger("app.utils.retry")

# Exceptions that must NEVER be retried
NON_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    AuthenticationError,
    AuthorizationError,
    YouTubeQuotaExceededError,
)


async def retry_with_backoff(
    coro_func: Callable[..., Coroutine[Any, Any, Any]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: bool = True,
    retryable_exceptions: Sequence[type[Exception]] | None = None,
    **kwargs: Any,
) -> Any:
    """
    Execute a coroutine with exponential backoff and randomized jitter.
    Fails fast without retrying for authentication, authorization, and quota errors.
    """
    attempt = 0
    while True:
        try:
            return await coro_func(*args, **kwargs)
        except Exception as exc:
            # Check non-retryable fatal exceptions
            if isinstance(exc, NON_RETRYABLE_EXCEPTIONS):
                logger.debug(f"Non-retryable exception encountered ({type(exc).__name__}): {exc}")
                raise

            # Check if exception type is explicitly non-retryable
            if retryable_exceptions is not None and not isinstance(exc, tuple(retryable_exceptions)):
                raise

            attempt += 1
            if attempt > max_retries:
                logger.error(f"Operation failed after {max_retries} retry attempts: {exc}")
                raise

            # Calculate backoff delay with exponential factor
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay = delay * random.uniform(0.5, 1.5)

            logger.warning(
                f"Attempt {attempt}/{max_retries} failed ({type(exc).__name__}: {exc}). "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

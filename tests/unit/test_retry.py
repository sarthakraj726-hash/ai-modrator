"""Unit tests for exponential backoff and jitter retry mechanism."""

import pytest

from app.core.exceptions import AuthenticationError
from app.utils.retry import retry_with_backoff


@pytest.mark.asyncio
async def test_retry_success_after_transient_failure():
    attempts = 0

    async def transient_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Temporary glitch")
        return "success"

    result = await retry_with_backoff(
        transient_operation,
        max_retries=3,
        base_delay=0.01,
        max_delay=0.1,
    )
    assert result == "success"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_non_retryable_fatal_exceptions():
    attempts = 0

    async def unauthenticated_call():
        nonlocal attempts
        attempts += 1
        raise AuthenticationError("Invalid Token")

    with pytest.raises(AuthenticationError):
        await retry_with_backoff(
            unauthenticated_call,
            max_retries=3,
            base_delay=0.01,
        )

    # Must fail immediately without retrying
    assert attempts == 1

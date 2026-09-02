"""Unit tests for RateLimiter."""

import pytest

from app.cache.rate_limiter import RateLimiter
from app.core.exceptions import RateLimitExceededError


@pytest.mark.asyncio
async def test_rate_limiter_allow_and_block():
    limiter = RateLimiter(key_prefix="test_rate")

    # Allow up to 3 requests per 60s
    assert await limiter.is_allowed("user-1", max_requests=3, window_seconds=60)
    assert await limiter.is_allowed("user-1", max_requests=3, window_seconds=60)
    assert await limiter.is_allowed("user-1", max_requests=3, window_seconds=60)

    # 4th request exceeds limit
    assert not await limiter.is_allowed("user-1", max_requests=3, window_seconds=60)

    with pytest.raises(RateLimitExceededError):
        await limiter.check("user-1", max_requests=3, window_seconds=60)

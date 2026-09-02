"""High-concurrency quota reservation stress tests."""

import asyncio

import pytest

from app.core.exceptions import YouTubeQuotaExceededError
from app.youtube.quota import QuotaManager


@pytest.mark.asyncio
async def test_quota_concurrent_atomic_reservations_stress():
    """
    Stress test: 50 concurrent tasks simultaneously attempting quota reservation
    under a tight budget (e.g. 100 units).
    Verifies that total consumed units NEVER exceed the configured daily budget,
    and race conditions are prevented atomically.
    """
    quota_mgr = QuotaManager(daily_limit=100)
    await quota_mgr.reset_daily_quota()

    successful_reservations = []
    rejected_reservations = []

    async def worker_task(worker_id: int):
        try:
            # Attempt to reserve 5 units
            res_id = await quota_mgr.reserve(units=5, method="videos.list")
            await quota_mgr.consume(res_id, method="videos.list")
            successful_reservations.append(res_id)
        except YouTubeQuotaExceededError:
            rejected_reservations.append(worker_id)

    # Launch 50 concurrent tasks (50 * 5 = 250 units requested vs 100 unit limit)
    tasks = [asyncio.create_task(worker_task(i)) for i in range(50)]
    await asyncio.gather(*tasks)

    used = await quota_mgr.get_used()
    # Verified: exactly 100 units consumed (20 successful tasks * 5 units)
    assert used == 100
    assert len(successful_reservations) == 20
    assert len(rejected_reservations) == 30

    # Quota is exhausted -> subsequent reservations fail immediately
    assert await quota_mgr.can_execute(units=1) is False
    with pytest.raises(YouTubeQuotaExceededError):
        await quota_mgr.reserve(units=1)

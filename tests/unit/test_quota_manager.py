"""Unit tests for YouTube QuotaManager."""

import pytest

from app.core.exceptions import YouTubeQuotaExceededError
from app.youtube.quota import QuotaManager


@pytest.mark.asyncio
async def test_quota_reservation_and_consumption():
    qm = QuotaManager(daily_limit=100)
    await qm.reset_daily_quota()

    assert await qm.remaining() == 100
    assert await qm.can_execute(50)

    # Reserve 50 units
    res_id = await qm.reserve(50)
    assert res_id is not None

    # Consume reservation
    total = await qm.consume(res_id)
    assert total == 50
    assert await qm.remaining() == 50
    assert await qm.percentage_used() == 50.0


@pytest.mark.asyncio
async def test_quota_hard_cap_enforcement():
    qm = QuotaManager(daily_limit=100)
    await qm.reset_daily_quota()

    # Reserve & consume 90 units
    res1 = await qm.reserve(90)
    await qm.consume(res1)

    assert await qm.remaining() == 10
    assert not await qm.can_execute(20)

    # Attempting to reserve 20 units must raise YouTubeQuotaExceededError
    with pytest.raises(YouTubeQuotaExceededError) as exc_info:
        await qm.reserve(20)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_quota_release_before_request():
    qm = QuotaManager(daily_limit=100)
    await qm.reset_daily_quota()

    res_id = await qm.reserve(40)
    await qm.release_if_failed_before_request(res_id)

    # Quota was not consumed
    assert await qm.get_used() == 0
    assert await qm.remaining() == 100

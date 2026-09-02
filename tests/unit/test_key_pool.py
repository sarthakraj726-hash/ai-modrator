"""Unit tests for YouTube ApiKeyPool."""

import pytest

from app.core.exceptions import YouTubeKeyPoolExhaustedError
from app.youtube.key_pool import ApiKeyPool, KeyStatus


@pytest.mark.asyncio
async def test_key_pool_least_used_rotation():
    pool = ApiKeyPool(keys=["key_A", "key_B"])

    # Initially key_A or key_B (both 0 usage)
    k1 = await pool.get_available_key()
    assert k1 in ("key_A", "key_B")

    # Increment usage on selected key
    await pool.record_usage(k1, units=50)

    # Next key should be the other key (usage 0)
    k2 = await pool.get_available_key()
    assert k2 != k1


@pytest.mark.asyncio
async def test_key_pool_error_cooldown_and_exhaustion():
    pool = ApiKeyPool(keys=["key_1"])

    key = await pool.get_available_key()
    assert key == "key_1"

    # Record 500 error placing key in cooldown
    await pool.record_error(key, status_code=500, error_message="Internal Server Error")
    status = pool.get_pool_status()[0]
    assert status["status"] == KeyStatus.COOLDOWN.value

    # Getting key when all are in cooldown raises YouTubeKeyPoolExhaustedError
    with pytest.raises(YouTubeKeyPoolExhaustedError):
        await pool.get_available_key()

"""Chaos and fault-injection tests for YouTube key pool and WebSub webhooks."""

import pytest

from app.core.exceptions import InvalidArgumentError, YouTubeKeyPoolExhaustedError
from app.youtube.key_pool import ApiKeyPool, KeyStatus
from app.youtube.websub.parser import WebSubParser


@pytest.mark.asyncio
async def test_key_pool_cascade_failure_and_exhaustion():
    """
    Simulate key failure cascade across 3 keys:
    - Key 1 receives 401 (Auth error) -> marked INVALID
    - Traffic shifts to Key 2 -> receives 429 (Rate limit) -> placed in COOLDOWN
    - Traffic shifts to Key 3 -> receives 503 (Unavailable) -> placed in COOLDOWN
    - System raises YouTubeKeyPoolExhaustedError safely.
    """
    pool = ApiKeyPool(keys=["key_alpha_1", "key_beta_2", "key_gamma_3"])

    # 1. First key selected
    k1 = await pool.get_available_key()
    assert k1 in ("key_alpha_1", "key_beta_2", "key_gamma_3")

    # Key 1 fails with 401
    await pool.record_error(k1, status_code=401, error_message="Invalid API Key")
    assert pool._keys[k1].status == KeyStatus.INVALID

    # 2. Next key selected
    k2 = await pool.get_available_key()
    assert k2 != k1

    # Key 2 fails with 429
    await pool.record_error(k2, status_code=429, error_message="Rate limit exceeded")
    assert pool._keys[k2].status == KeyStatus.COOLDOWN

    # 3. Third key selected
    k3 = await pool.get_available_key()
    assert k3 not in (k1, k2)

    # Key 3 fails with 503
    await pool.record_error(k3, status_code=503, error_message="Service unavailable")
    assert pool._keys[k3].status == KeyStatus.COOLDOWN

    # 4. Now all keys are unavailable -> must raise YouTubeKeyPoolExhaustedError
    with pytest.raises(YouTubeKeyPoolExhaustedError):
        await pool.get_available_key()


def test_websub_xml_bomb_and_malformed_chaos():
    """Verify parser rejects malformed and malicious XML."""
    with pytest.raises(InvalidArgumentError):
        WebSubParser.parse_atom_feed("<feed><entry>missing closing tags")

    with pytest.raises(InvalidArgumentError):
        WebSubParser.parse_atom_feed("not xml at all")

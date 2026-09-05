"""Unit tests for YouTube OAuth token management and KeyPool OAuth error protection."""

import pytest
from unittest.mock import AsyncMock

from app.youtube.key_pool import ApiKeyPool, KeyStatus
from app.youtube.oauth import YouTubeOAuthManager


@pytest.mark.asyncio
async def test_oauth_manager_save_and_retrieve():
    fake_redis = AsyncMock()
    stored_data = {}

    async def mock_get(key):
        return stored_data.get(key)

    async def mock_set(key, val, **kwargs):
        stored_data[key] = val

    async def mock_delete(key):
        stored_data.pop(key, None)

    fake_redis.get = mock_get
    fake_redis.set = mock_set
    fake_redis.delete = mock_delete

    mgr = YouTubeOAuthManager(redis_client=fake_redis)

    # 1. Save access token
    await mgr.save_bot_token("ya29.custom_test_access_token", is_refresh_token=False)
    tok = await mgr.get_access_token()
    assert tok == "ya29.custom_test_access_token"

    # 2. Clear token
    await mgr.clear_bot_token()
    assert mgr._cached_access_token is None


@pytest.mark.asyncio
async def test_key_pool_does_not_poison_on_oauth_401():
    pool = ApiKeyPool(keys=["AIzaSyValidKey1234567890"])

    # Normal 401 with OAuth required message
    await pool.record_error(
        key="AIzaSyValidKey1234567890",
        status_code=401,
        error_message="API keys are not supported by this API. Expected OAuth2 access token or other authentication credentials that assert a principal.",
    )

    # Key must remain AVAILABLE, not INVALID!
    meta = pool._keys["AIzaSyValidKey1234567890"]
    assert meta is not None
    assert meta.status == KeyStatus.AVAILABLE

    # Genuine invalid key 401 error
    await pool.record_error(
        key="AIzaSyValidKey1234567890",
        status_code=401,
        error_message="API key expired or revoked.",
    )
    assert meta.status == KeyStatus.INVALID



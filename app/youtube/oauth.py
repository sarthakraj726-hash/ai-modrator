"""YouTube OAuth Token Management supporting static access tokens and auto-refresh."""

import time
from typing import Any
import httpx

from app.cache.redis import RedisClient, get_redis_sync
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.youtube.oauth")

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIS_OAUTH_ACCESS_KEY = "youtube:bot:oauth_access_token"
REDIS_OAUTH_REFRESH_KEY = "youtube:bot:oauth_refresh_token"


class YouTubeOAuthManager:
    """
    Manages OAuth 2.0 credentials for the YouTube bot channel.
    YouTube Data API v3 strictly requires OAuth 2.0 (scope youtube or youtube.force-ssl)
    to insert live chat messages, post moderation warnings, or perform timeouts.
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        self.redis_client = redis_client or get_redis_sync()
        self._cached_access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str | None:
        """
        Return a valid OAuth 2.0 access token if configured.
        Resolution order:
        1. Test-mode bypass (returns mock token in test mode if none configured)
        2. In-memory unexpired token
        3. Redis cached access token
        4. Settings static YOUTUBE_OAUTH_TOKEN
        5. Auto-refresh via YOUTUBE_REFRESH_TOKEN / Redis refresh token
        """
        settings = get_settings()
        now = time.time()

        # 1. Test-mode bypass
        if settings.is_testing and not self._cached_access_token and not settings.YOUTUBE_OAUTH_TOKEN:
            return "mock_testing_oauth_token"

        # 2. In-memory check
        if self._cached_access_token and now < (self._token_expires_at - 60):
            return self._cached_access_token

        # 3. Redis cached token
        try:
            redis_tok = await self.redis_client.get(REDIS_OAUTH_ACCESS_KEY)
            if redis_tok:
                self._cached_access_token = redis_tok
                self._token_expires_at = now + 1800
                return redis_tok
        except Exception as e:
            logger.debug(f"Redis get oauth token error: {e}")

        # 4. Environment static token
        if settings.YOUTUBE_OAUTH_TOKEN and settings.YOUTUBE_OAUTH_TOKEN.strip():
            tok = settings.YOUTUBE_OAUTH_TOKEN.strip()
            self._cached_access_token = tok
            self._token_expires_at = now + 3600
            return tok

        # 5. Refresh token flow
        refresh_tok = None
        try:
            refresh_tok = await self.redis_client.get(REDIS_OAUTH_REFRESH_KEY)
        except Exception:
            pass

        if not refresh_tok and getattr(settings, "YOUTUBE_REFRESH_TOKEN", None):
            refresh_tok = settings.YOUTUBE_REFRESH_TOKEN.strip()

        client_id = getattr(settings, "YOUTUBE_CLIENT_ID", "")
        client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", "")

        if refresh_tok and client_id and client_secret:
            refreshed = await self.refresh_access_token(
                client_id=client_id.strip(),
                client_secret=client_secret.strip(),
                refresh_token=refresh_tok,
            )
            if refreshed:
                return refreshed

        return None

    async def refresh_access_token(
        self, client_id: str, client_secret: str, refresh_token: str
    ) -> str | None:
        """Exchange refresh token for fresh access token via Google OAuth2."""
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(GOOGLE_OAUTH_TOKEN_URL, data=data)
                if res.status_code == 200:
                    payload = res.json()
                    access_token = payload.get("access_token")
                    expires_in = int(payload.get("expires_in", 3600))
                    if access_token:
                        self._cached_access_token = access_token
                        self._token_expires_at = time.time() + expires_in
                        try:
                            await self.redis_client.set(
                                REDIS_OAUTH_ACCESS_KEY, access_token, ttl=max(60, expires_in - 120)
                            )
                        except Exception:
                            pass
                        logger.info("Successfully refreshed YouTube bot OAuth access token.")
                        return access_token
                else:
                    logger.warning(
                        f"Failed to refresh YouTube OAuth token: HTTP {res.status_code} - {res.text}"
                    )
        except Exception as exc:
            logger.warning(f"Exception while refreshing YouTube OAuth token: {exc}")
        return None

    async def save_bot_token(self, token: str, is_refresh_token: bool = False) -> None:
        """Store bot token into Redis and in-memory cache."""
        cleaned = token.strip()
        if not cleaned:
            return
        if is_refresh_token:
            await self.redis_client.set(REDIS_OAUTH_REFRESH_KEY, cleaned, ttl=86400 * 90)
            settings = get_settings()
            client_id = getattr(settings, "YOUTUBE_CLIENT_ID", "")
            client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", "")
            if client_id and client_secret:
                await self.refresh_access_token(client_id, client_secret, cleaned)
        else:
            await self.redis_client.set(REDIS_OAUTH_ACCESS_KEY, cleaned, ttl=3500)
            self._cached_access_token = cleaned
            self._token_expires_at = time.time() + 3500
            logger.info("Saved new YouTube bot OAuth access token to memory and Redis.")

    async def clear_bot_token(self) -> None:
        """Revoke/clear cached bot token."""
        self._cached_access_token = None
        self._token_expires_at = 0.0
        try:
            await self.redis_client.delete(REDIS_OAUTH_ACCESS_KEY)
            await self.redis_client.delete(REDIS_OAUTH_REFRESH_KEY)
        except Exception:
            pass


_global_oauth_manager: YouTubeOAuthManager | None = None


def get_oauth_manager() -> YouTubeOAuthManager:
    """Return singleton YouTubeOAuthManager."""
    global _global_oauth_manager
    if _global_oauth_manager is None:
        _global_oauth_manager = YouTubeOAuthManager()
    return _global_oauth_manager

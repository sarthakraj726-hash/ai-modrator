"""YouTube API Key Pool with health tracking, error cooldowns, and load distribution."""

import asyncio
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import YouTubeKeyPoolExhaustedError
from app.core.logging import get_logger

logger = get_logger("app.youtube.key_pool")


class KeyStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    COOLDOWN = "COOLDOWN"
    EXHAUSTED = "EXHAUSTED"
    INVALID = "INVALID"


class KeyMetadata(BaseModel):
    key: str
    masked_key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    estimated_usage: int = 0
    consecutive_errors: int = 0
    last_error: str | None = None
    last_error_code: int | None = None
    cooldown_until: float = 0.0


def mask_key(key: str) -> str:
    """Mask key string for safe logging and status reporting."""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class ApiKeyPool:
    """
    Manages a pool of YouTube API keys for reliability and controlled budgeting.
    Rotates keys based on least-used heuristic and isolates unhealthy keys in cooldown.
    """

    def __init__(self, keys: list[str] | None = None):
        settings = get_settings()
        raw_keys = keys if keys is not None else settings.youtube_api_keys
        # Ensure fallback key for mock/local development if no keys provided
        if not raw_keys:
            raw_keys = ["mock-youtube-dev-key-1"]

        self._keys: dict[str, KeyMetadata] = {}
        for k in raw_keys:
            k_clean = k.strip()
            if k_clean:
                self._keys[k_clean] = KeyMetadata(
                    key=k_clean,
                    masked_key=mask_key(k_clean),
                )
        self._lock = asyncio.Lock()

    async def get_available_key(self) -> str:
        """
        Select an available API key using least-used balancing.
        Raises YouTubeKeyPoolExhaustedError if all keys are unavailable.
        """
        async with self._lock:
            now = time.time()

            # Refresh keys whose cooldown period has expired
            for meta in self._keys.values():
                if meta.status == KeyStatus.COOLDOWN and now >= meta.cooldown_until:
                    logger.info(f"API key {meta.masked_key} cooldown expired. Returning to AVAILABLE status.")
                    meta.status = KeyStatus.AVAILABLE
                    meta.consecutive_errors = 0

            available = [
                meta for meta in self._keys.values()
                if meta.status == KeyStatus.AVAILABLE
            ]

            if not available:
                logger.error("No available YouTube API keys found in pool.")
                raise YouTubeKeyPoolExhaustedError()

            # Select key with lowest estimated usage
            selected = min(available, key=lambda m: m.estimated_usage)
            return selected.key

    async def record_usage(self, key: str, units: int = 1) -> None:
        """Increment usage estimation for the selected key."""
        async with self._lock:
            if key in self._keys:
                self._keys[key].estimated_usage += units

    async def record_success(self, key: str) -> None:
        """Reset consecutive error count for healthy key."""
        async with self._lock:
            if key in self._keys:
                self._keys[key].consecutive_errors = 0
                if self._keys[key].status == KeyStatus.AVAILABLE:
                    self._keys[key].last_error = None

    async def record_error(self, key: str, status_code: int, error_message: str) -> None:
        """
        Handle API error response:
        - 400 / 403 (quota/disabled): Mark EXHAUSTED or INVALID
        - 429 / 5xx: Place in temporary cooldown
        """
        async with self._lock:
            if key not in self._keys:
                return

            meta = self._keys[key]
            meta.consecutive_errors += 1
            meta.last_error = error_message
            meta.last_error_code = status_code
            now = time.time()

            if status_code in (401, 403) and "quota" in error_message.lower():
                meta.status = KeyStatus.EXHAUSTED
                meta.cooldown_until = now + 86400  # 24h
                logger.warning(f"Key {meta.masked_key} marked EXHAUSTED due to provider quota breach: {error_message}")
            elif status_code in (401, 403):
                meta.status = KeyStatus.INVALID
                logger.error(f"Key {meta.masked_key} marked INVALID (Auth failure: {error_message})")
            else:
                # Temporary backoff cooldown (30s, 60s, 120s based on consecutive errors)
                cooldown_duration = min(300, 30 * (2 ** (meta.consecutive_errors - 1)))
                meta.status = KeyStatus.COOLDOWN
                meta.cooldown_until = now + cooldown_duration
                logger.warning(
                    f"Key {meta.masked_key} placed in COOLDOWN for {cooldown_duration}s (HTTP {status_code}: {error_message})"
                )

    def get_pool_status(self) -> list[dict[str, Any]]:
        """Return public status summary of all keys in pool."""
        now = time.time()
        return [
            {
                "masked_key": meta.masked_key,
                "status": meta.status.value,
                "estimated_usage": meta.estimated_usage,
                "consecutive_errors": meta.consecutive_errors,
                "last_error": meta.last_error,
                "cooldown_remaining_seconds": max(0, int(meta.cooldown_until - now)) if meta.status == KeyStatus.COOLDOWN else 0,
            }
            for meta in self._keys.values()
        ]


_global_key_pool: ApiKeyPool | None = None


def get_key_pool() -> ApiKeyPool:
    """Return the singleton ApiKeyPool."""
    global _global_key_pool
    if _global_key_pool is None:
        _global_key_pool = ApiKeyPool()
    return _global_key_pool

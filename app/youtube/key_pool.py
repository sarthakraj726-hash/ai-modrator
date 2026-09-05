"""YouTube API Key Pool with health tracking, error cooldowns, and load distribution."""

import asyncio
import hashlib
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
    slot: str  # e.g., "key_1", "key_2", "key_3"
    key: str
    key_hash: str
    masked_key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    total_requests: int = 0
    successful_requests: int = 0
    estimated_usage: int = 0
    consecutive_errors: int = 0
    failures_401: int = 0
    failures_403: int = 0
    failures_429: int = 0
    failures_5xx: int = 0
    last_error: str | None = None
    last_error_code: int | None = None
    last_success: float | None = None
    last_failure: float | None = None
    cooldown_until: float = 0.0


def mask_key(key: str) -> str:
    """Mask key string for safe logging and status reporting."""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class ApiKeyPool:
    """
    Manages a pool of YouTube API keys (YOUTUBE_API_KEY_1, YOUTUBE_API_KEY_2, YOUTUBE_API_KEY_3)
    for high reliability, least-used load balancing, and error cooldown isolation.
    """

    def __init__(self, keys: list[str] | None = None) -> None:
        settings = get_settings()
        raw_keys = keys if keys is not None else settings.youtube_api_keys
        if not raw_keys:
            raw_keys = ["mock-youtube-dev-key-1"]

        self._keys: dict[str, KeyMetadata] = {}
        for idx, k in enumerate(raw_keys, start=1):
            k_clean = k.strip()
            if k_clean:
                k_hash = hashlib.sha256(k_clean.encode()).hexdigest()[:12]
                self._keys[k_clean] = KeyMetadata(
                    slot=f"key_{idx}",
                    key=k_clean,
                    key_hash=k_hash,
                    masked_key=mask_key(k_clean),
                )
        self._lock = asyncio.Lock()

    async def get_available_key(self) -> str:
        """
        Select an available API key using least-used balancing.
        Raises YouTubeKeyPoolExhaustedError if all keys are in cooldown, exhausted, or invalid.
        """
        async with self._lock:
            now = time.time()

            # Refresh keys whose cooldown period has expired
            for meta in self._keys.values():
                if meta.status == KeyStatus.COOLDOWN and now >= meta.cooldown_until:
                    logger.info(
                        f"API key slot {meta.slot} ({meta.masked_key}) cooldown expired. Returning to AVAILABLE status."
                    )
                    meta.status = KeyStatus.AVAILABLE
                    meta.consecutive_errors = 0

            available = [meta for meta in self._keys.values() if meta.status == KeyStatus.AVAILABLE]

            if not available:
                logger.error(
                    "No available YouTube API keys found in pool (all in cooldown, exhausted, or invalid)."
                )
                raise YouTubeKeyPoolExhaustedError()

            # Select key with lowest estimated usage
            selected = min(available, key=lambda m: m.estimated_usage)
            selected.total_requests += 1
            return selected.key

    async def record_usage(self, key: str, units: int = 1) -> None:
        """Increment usage estimation for the selected key."""
        async with self._lock:
            if key in self._keys:
                self._keys[key].estimated_usage += units

    async def record_success(self, key: str) -> None:
        """Reset consecutive error count and record success timestamp."""
        async with self._lock:
            if key in self._keys:
                meta = self._keys[key]
                meta.consecutive_errors = 0
                meta.successful_requests += 1
                meta.last_success = time.time()
                if meta.status == KeyStatus.AVAILABLE:
                    meta.last_error = None

    async def record_error(self, key: str, status_code: int, error_message: str) -> None:
        """
        Handle API error response:
        - 401: Key invalid
        - 403 quotaExceeded: Key exhausted
        - 429: Key placed in cooldown
        - 5xx: Key placed in cooldown with exponential backoff
        """
        async with self._lock:
            if key not in self._keys:
                return

            meta = self._keys[key]
            meta.consecutive_errors += 1
            meta.last_error = error_message
            meta.last_error_code = status_code
            now = time.time()
            meta.last_failure = now

            if status_code == 401:
                # Do not invalidate API keys if error is due to endpoint requiring OAuth principal
                if (
                    "API keys are not supported" in error_message
                    or "CREDENTIALS_MISSING" in error_message
                    or "Login Required" in error_message
                    or "OAuth" in error_message
                ):
                    logger.warning(
                        f"API key slot {meta.slot} ({meta.masked_key}) received 401 on OAuth-required endpoint. Key remains {meta.status.value}."
                    )
                    return

                meta.failures_401 += 1
                meta.status = KeyStatus.INVALID
                logger.error(
                    f"Key slot {meta.slot} ({meta.masked_key}) marked INVALID (Auth 401: {error_message})"
                )
            elif status_code == 403:
                meta.failures_403 += 1
                if "quota" in error_message.lower():
                    meta.status = KeyStatus.EXHAUSTED
                    meta.cooldown_until = now + 86400  # 24 hours
                    logger.warning(
                        f"Key slot {meta.slot} ({meta.masked_key}) marked EXHAUSTED due to provider quota: {error_message}"
                    )
                else:
                    # Forbidden permission error
                    meta.status = KeyStatus.COOLDOWN
                    meta.cooldown_until = now + 300
                    logger.warning(
                        f"Key slot {meta.slot} ({meta.masked_key}) placed in COOLDOWN for 300s (HTTP 403: {error_message})"
                    )
            elif status_code == 429:
                meta.failures_429 += 1
                cooldown_duration = min(300, 30 * (2 ** (meta.consecutive_errors - 1)))
                meta.status = KeyStatus.COOLDOWN
                meta.cooldown_until = now + cooldown_duration
                logger.warning(
                    f"Key slot {meta.slot} ({meta.masked_key}) placed in COOLDOWN for {cooldown_duration}s (HTTP 429 Rate Limit)"
                )
            else:
                meta.failures_5xx += 1
                cooldown_duration = min(300, 15 * (2 ** (meta.consecutive_errors - 1)))
                meta.status = KeyStatus.COOLDOWN
                meta.cooldown_until = now + cooldown_duration
                logger.warning(
                    f"Key slot {meta.slot} ({meta.masked_key}) placed in COOLDOWN for {cooldown_duration}s (HTTP {status_code}: {error_message})"
                )

    def get_pool_status(self) -> list[dict[str, Any]]:
        """Return public status summary of all keys in pool without raw secrets."""
        now = time.time()
        return [
            {
                "slot": meta.slot,
                "key_hash": meta.key_hash,
                "masked_key": meta.masked_key,
                "status": meta.status.value,
                "total_requests": meta.total_requests,
                "successful_requests": meta.successful_requests,
                "estimated_usage": meta.estimated_usage,
                "consecutive_errors": meta.consecutive_errors,
                "failures_401": meta.failures_401,
                "failures_403": meta.failures_403,
                "failures_429": meta.failures_429,
                "failures_5xx": meta.failures_5xx,
                "last_error": meta.last_error,
                "cooldown_remaining_seconds": max(0, int(meta.cooldown_until - now))
                if meta.status == KeyStatus.COOLDOWN
                else 0,
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

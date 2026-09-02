"""Pydantic schemas for YouTube engine diagnostics and management."""

from typing import Any

from pydantic import BaseModel


class YouTubeKeyStatusItem(BaseModel):
    slot: str
    key_hash: str
    masked_key: str
    status: str
    total_requests: int
    successful_requests: int
    estimated_usage: int
    consecutive_errors: int
    failures_401: int
    failures_403: int
    failures_429: int
    failures_5xx: int
    last_error: str | None = None
    cooldown_remaining_seconds: int = 0


class YouTubeKeysResponse(BaseModel):
    total_keys: int
    available_keys: int
    cooldown_keys: int
    exhausted_keys: int
    invalid_keys: int
    keys: list[YouTubeKeyStatusItem]


class YouTubeQuotaResponse(BaseModel):
    daily_budget: int
    estimated_used: int
    remaining: int
    percentage_used: float
    requests_by_method: dict[str, Any]
    active_reservations_count: int


class YouTubeDiscoveryStatusResponse(BaseModel):
    running: bool
    discovery_attempts: int
    discovery_success: int
    discovery_failures: int


class YouTubeStatusResponse(BaseModel):
    status: str = "operational"
    daily_budget: int
    remaining_quota: int
    percentage_quota_used: float
    key_pool_total: int
    key_pool_available: int
    discovery_active: bool
    active_stream_sessions: int

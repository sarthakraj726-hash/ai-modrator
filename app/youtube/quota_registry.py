"""Centralized YouTube Quota Cost Registry."""

import os
from typing import Any

from pydantic import BaseModel


class MethodQuotaStats(BaseModel):
    method: str
    cost_per_call: int
    total_calls: int = 0
    total_quota_consumed: int = 0
    failed_calls: int = 0


class YouTubeQuotaCostRegistry:
    """Registry for YouTube API method costs and usage telemetry."""

    # Default Google YouTube Data API v3 quota costs
    DEFAULT_METHOD_COSTS: dict[str, int] = {
        "videos.list": 1,
        "channels.list": 1,
        "liveBroadcasts.list": 1,
        "liveChatMessages.list": 1,
        "liveChatMessages.streamList": 1,
        "liveChatMessages.insert": 50,
        "liveChatModerators.list": 1,
        "liveChatBans.insert": 50,
        "search.list": 100,
        "default": 1,
    }

    def __init__(self) -> None:
        self._method_costs: dict[str, int] = dict(self.DEFAULT_METHOD_COSTS)
        self._stats: dict[str, MethodQuotaStats] = {}
        self._load_environment_overrides()

    def _load_environment_overrides(self) -> None:
        """Load environment overrides such as YOUTUBE_QUOTA_COST_VIDEOS_LIST."""
        for method, _default_cost in self.DEFAULT_METHOD_COSTS.items():
            env_var = f"YOUTUBE_QUOTA_COST_{method.upper().replace('.', '_')}"
            override = os.getenv(env_var)
            if override is not None:
                try:
                    self._method_costs[method] = int(override)
                except ValueError:
                    pass

    def get_cost(self, method: str) -> int:
        """Return configured quota cost for a YouTube API method."""
        return self._method_costs.get(method, self._method_costs.get("default", 1))

    def set_cost(self, method: str, cost: int) -> None:
        """Dynamically override quota cost for a method."""
        self._method_costs[method] = cost

    def record_usage(self, method: str, cost: int, success: bool = True) -> None:
        """Record telemetry for method execution."""
        if method not in self._stats:
            self._stats[method] = MethodQuotaStats(method=method, cost_per_call=cost)

        stat = self._stats[method]
        stat.total_calls += 1
        stat.total_quota_consumed += cost
        if not success:
            stat.failed_calls += 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Return snapshot of per-method telemetry."""
        return {method: stat.model_dump() for method, stat in self._stats.items()}

    def reset_stats(self) -> None:
        """Reset internal telemetry counters."""
        self._stats.clear()


# Global default quota cost registry
quota_cost_registry = YouTubeQuotaCostRegistry()

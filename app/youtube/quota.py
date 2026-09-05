"""YouTube Data API v3 quota manager enforcing hard application budget."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.exceptions import YouTubeQuotaExceededError
from app.core.logging import get_logger
from app.youtube.models import RequestClassification
from app.youtube.quota_registry import quota_cost_registry

logger = get_logger("app.youtube.quota")


class QuotaReservation:
    """Represents a temporary two-phase quota reservation."""

    def __init__(self, reservation_id: str, units: int, method: str, created_at: float) -> None:
        self.reservation_id = reservation_id
        self.units = units
        self.method = method
        self.created_at = created_at
        self.consumed = False
        self.released = False


class QuotaManager:
    """
    Enforces a strict configurable application-level daily budget cap
    (e.g., YOUTUBE_QUOTA_DAILY_LIMIT=40000) on YouTube API consumption.
    All YouTube API requests must pass through this layer.
    """

    def __init__(self, daily_limit: int | None = None) -> None:
        settings = get_settings()
        self.daily_limit = daily_limit or settings.YOUTUBE_QUOTA_DAILY_LIMIT
        self._reservations: dict[str, QuotaReservation] = {}
        self._lock = asyncio.Lock()

    def _get_daily_key(self) -> str:
        today_utc = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"quota:youtube:{today_utc}"

    async def get_used(self) -> int:
        """Return total units consumed so far today."""
        redis = await get_redis_client()
        key = self._get_daily_key()
        val = await redis.get(key)
        return int(val) if val is not None else 0

    async def remaining(self) -> int:
        """Return remaining units under the daily budget."""
        used = await self.get_used()
        return max(0, self.daily_limit - used)

    async def percentage_used(self) -> float:
        """Return quota utilization as a percentage (0.0 to 100.0)."""
        used = await self.get_used()
        if self.daily_limit <= 0:
            return 100.0
        return min(100.0, round((used / self.daily_limit) * 100.0, 2))

    async def can_execute(self, units: int | None = None, method: str | None = None) -> bool:
        """Check if enough quota remains to execute an operation."""
        if units is None:
            units = quota_cost_registry.get_cost(method or "default")
        rem = await self.remaining()
        return rem >= units

    async def reserve(self, units: int | None = None, method: str = "videos.list") -> str:
        """
        Two-phase commit reservation.
        Checks quota limit and holds quota before making network request.
        Raises YouTubeQuotaExceededError if hard budget would be exceeded.
        """
        if units is None:
            units = quota_cost_registry.get_cost(method)

        async with self._lock:
            used = await self.get_used()
            # Account for currently active uncommitted reservations
            active_reserved = sum(
                r.units for r in self._reservations.values() if not r.consumed and not r.released
            )
            if used + active_reserved + units > self.daily_limit:
                logger.error(
                    f"Quota allocation rejected: Requested {units} units for '{method}', "
                    f"but used/reserved {used + active_reserved}/{self.daily_limit}"
                )
                raise YouTubeQuotaExceededError(
                    current_used=used + active_reserved, max_limit=self.daily_limit
                )

            reservation_id = str(uuid.uuid4())
            loop = asyncio.get_event_loop()
            self._reservations[reservation_id] = QuotaReservation(
                reservation_id=reservation_id,
                units=units,
                method=method,
                created_at=loop.time(),
            )
            logger.debug(
                f"Reserved {units} quota units for '{method}' (Reservation ID: {reservation_id[:8]})"
            )
            return reservation_id

    async def consume(self, reservation_id: str, method: str | None = None) -> int:
        """
        Confirm execution of request and record units in persistent daily counter.
        """
        async with self._lock:
            reservation = self._reservations.get(reservation_id)
            if not reservation:
                logger.warning(f"Attempted to consume unknown reservation '{reservation_id}'")
                return 0

            if reservation.consumed:
                return reservation.units

            reservation.consumed = True
            redis = await get_redis_client()
            key = self._get_daily_key()
            new_total = await redis.incrby(key, reservation.units)
            # Ensure daily key expires after 48 hours
            await redis.expire(key, 172800)

            # Record method telemetry in registry
            effective_method = method or reservation.method
            quota_cost_registry.record_usage(effective_method, reservation.units, success=True)

            # Clean up local reservation
            self._reservations.pop(reservation_id, None)

            logger.info(
                f"Consumed {reservation.units} YouTube quota units for '{effective_method}'. "
                f"Today's total: {new_total}/{self.daily_limit} ({self.percentage_used_from_total(new_total)}%)"
            )
            return new_total

    async def release_if_failed_before_request(self, reservation_id: str) -> None:
        """
        Release reservation without charging quota if request failed prior to network dispatch.
        """
        async with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            if reservation and not reservation.consumed:
                reservation.released = True
                logger.debug(
                    f"Released unconsumed reservation {reservation_id[:8]} ({reservation.units} units)"
                )

    async def release_if_not_dispatched(self, reservation_id: str) -> None:
        """Alias for release_if_failed_before_request."""
        await self.release_if_failed_before_request(reservation_id)

    async def record_failure(
        self,
        reservation_id: str,
        classification: RequestClassification = RequestClassification.REQUEST_SENT_NETWORK_FAILURE,
        method: str | None = None,
    ) -> None:
        """
        Record failed request. If request was never dispatched (REQUEST_NOT_SENT), release reservation.
        If request reached network (5xx, 429, timeout), consume quota conservatively.
        """
        if classification == RequestClassification.REQUEST_NOT_SENT:
            await self.release_if_not_dispatched(reservation_id)
        else:
            # Conservative quota accounting: request reached Google, charge quota
            await self.consume(reservation_id, method=method)
            effective_method = method or "default"
            quota_cost_registry.record_usage(effective_method, 0, success=False)

    def percentage_used_from_total(self, total: int) -> float:
        if self.daily_limit <= 0:
            return 100.0
        return min(100.0, round((total / self.daily_limit) * 100.0, 2))

    async def get_metrics(self) -> dict[str, Any]:
        """Return comprehensive diagnostics for developer quota dashboard."""
        used = await self.get_used()
        rem = max(0, self.daily_limit - used)
        pct = self.percentage_used_from_total(used)
        method_stats = quota_cost_registry.get_stats()
        return {
            "daily_budget": self.daily_limit,
            "estimated_used": used,
            "remaining": rem,
            "percentage_used": pct,
            "requests_by_method": method_stats,
            "active_reservations_count": len(
                [r for r in self._reservations.values() if not r.consumed and not r.released]
            ),
        }

    async def reset_daily_quota(self) -> None:
        """Manually reset current day's quota counter (for tests)."""
        redis = await get_redis_client()
        key = self._get_daily_key()
        await redis.delete(key)
        self._reservations.clear()


_global_quota_manager: QuotaManager | None = None


def get_quota_manager() -> QuotaManager:
    """Return the singleton QuotaManager instance."""
    global _global_quota_manager
    if _global_quota_manager is None:
        _global_quota_manager = QuotaManager()
    return _global_quota_manager

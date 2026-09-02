"""YouTube Data API v3 quota manager enforcing hard 4,000 units/day budget."""

import asyncio
import uuid
from datetime import UTC, datetime

from app.cache.redis import get_redis_client
from app.core.config import get_settings
from app.core.exceptions import YouTubeQuotaExceededError
from app.core.logging import get_logger

logger = get_logger("app.youtube.quota")


class QuotaReservation:
    """Represents a temporary two-phase quota reservation."""
    def __init__(self, reservation_id: str, units: int, created_at: float):
        self.reservation_id = reservation_id
        self.units = units
        self.created_at = created_at
        self.consumed = False
        self.released = False


class QuotaManager:
    """
    Enforces a strict 4,000 units/day daily budget cap on YouTube API consumption.
    All YouTube API requests must pass through this layer.
    """

    def __init__(self, daily_limit: int | None = None):
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
        """Return remaining units under the 4,000 daily budget."""
        used = await self.get_used()
        return max(0, self.daily_limit - used)

    async def percentage_used(self) -> float:
        """Return quota utilization as a percentage (0.0 to 100.0)."""
        used = await self.get_used()
        if self.daily_limit <= 0:
            return 100.0
        return min(100.0, round((used / self.daily_limit) * 100.0, 2))

    async def can_execute(self, units: int = 1) -> bool:
        """Check if enough quota remains to execute an operation."""
        rem = await self.remaining()
        return rem >= units

    async def reserve(self, units: int = 1) -> str:
        """
        Two-phase commit reservation.
        Checks quota limit and holds quota before making network request.
        Raises YouTubeQuotaExceededError if hard budget would be exceeded.
        """
        async with self._lock:
            used = await self.get_used()
            if used + units > self.daily_limit:
                logger.error(
                    f"Quota allocation rejected: Requested {units} units, but used {used}/{self.daily_limit}"
                )
                raise YouTubeQuotaExceededError(current_used=used, max_limit=self.daily_limit)

            reservation_id = str(uuid.uuid4())
            loop = asyncio.get_event_loop()
            self._reservations[reservation_id] = QuotaReservation(
                reservation_id=reservation_id,
                units=units,
                created_at=loop.time(),
            )
            logger.debug(f"Reserved {units} quota units (Reservation ID: {reservation_id[:8]})")
            return reservation_id

    async def consume(self, reservation_id: str) -> int:
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

            # Clean up local reservation
            self._reservations.pop(reservation_id, None)

            logger.info(
                f"Consumed {reservation.units} YouTube quota units. "
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
                logger.debug(f"Released unconsumed reservation {reservation_id[:8]} ({reservation.units} units)")

    def percentage_used_from_total(self, total: int) -> float:
        if self.daily_limit <= 0:
            return 100.0
        return min(100.0, round((total / self.daily_limit) * 100.0, 2))

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

"""Creator-scoped XP progression engine with multi-layer anti-farming defenses."""

import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.engagement_repo import EngagementRepository

logger = get_logger("app.engagement.xp")


class AntiFarmingGuard:
    """
    Stateful anti-farming validator preventing automated script farming,
    character repetition, copy-paste spam, and burst flooding.
    """

    def __init__(
        self,
        cooldown_seconds: int = 60,
        min_message_length: int = 4,
        max_daily_xp: int = 2500,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.min_message_length = min_message_length
        self.max_daily_xp = max_daily_xp

        # In-memory tracking per (creator_id, viewer_id)
        # key: (creator_id, viewer_id) -> last_award_timestamp
        self._last_award: dict[tuple[str, str], float] = {}
        # key: (creator_id, viewer_id) -> list of award timestamps in current window
        self._award_timestamps: dict[tuple[str, str], list[float]] = {}
        # key: (creator_id, viewer_id) -> (date_str, daily_xp_total)
        self._daily_totals: dict[tuple[str, str], tuple[str, int]] = {}

    def is_message_meaningful(self, text: str) -> tuple[bool, str]:
        """Check if message content qualifies for XP reward."""
        cleaned = text.strip().lower()
        if len(cleaned) < self.min_message_length:
            return False, "MESSAGE_TOO_SHORT"

        # Check for single repeated character (e.g. "aaaaaa", "111111")
        if len(set(cleaned)) <= 2 and len(cleaned) > 5:
            return False, "REPETITIVE_CHARACTERS"

        # Check for repetitive word spam (e.g. "lol lol lol lol")
        words = cleaned.split()
        if len(words) >= 3 and len(set(words)) == 1:
            return False, "REPETITIVE_WORD_SPAM"

        # Check if text is just common emotes or laughter
        if re.fullmatch(r"^[😂🤣😆😅😹🔥❤️👍\s]+$", cleaned):
            return False, "EMOJI_ONLY"

        return True, "VALID"

    def can_award_xp(self, creator_id: str, viewer_id: str, xp_amount: int) -> tuple[bool, str]:
        """Validate cooldown, burst limit, and daily cap."""
        now = datetime.now(UTC).timestamp()
        key = (creator_id, viewer_id)

        # 1. Cooldown Check
        last_time = self._last_award.get(key, 0.0)
        if now - last_time < self.cooldown_seconds:
            return (
                False,
                f"COOLDOWN_ACTIVE (remaining: {int(self.cooldown_seconds - (now - last_time))}s)",
            )

        # 2. Burst Check (Max 6 awards per 10 minutes)
        window = 600.0
        timestamps = self._award_timestamps.setdefault(key, [])
        self._award_timestamps[key] = [t for t in timestamps if now - t < window]
        if len(self._award_timestamps[key]) >= 6:
            return False, "BURST_LIMIT_EXCEEDED"

        # 3. Daily Cap Check
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        recorded_date, current_daily = self._daily_totals.get(key, (today_str, 0))
        if recorded_date != today_str:
            current_daily = 0
            self._daily_totals[key] = (today_str, 0)

        if current_daily + xp_amount > self.max_daily_xp:
            return False, "DAILY_CAP_REACHED"

        return True, "ALLOWED"

    def record_award(self, creator_id: str, viewer_id: str, xp_amount: int) -> None:
        """Record successful award in anti-farming trackers."""
        now = datetime.now(UTC).timestamp()
        key = (creator_id, viewer_id)
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")

        self._last_award[key] = now
        self._award_timestamps.setdefault(key, []).append(now)

        _, current_daily = self._daily_totals.get(key, (today_str, 0))
        self._daily_totals[key] = (today_str, current_daily + xp_amount)


class XPManager:
    """
    Deterministic level progression and XP management.
    Formula: required_xp(level) = base_xp * (level ** multiplier)
    """

    def __init__(
        self,
        base_xp: int = 100,
        multiplier: float = 1.5,
        anti_farming: AntiFarmingGuard | None = None,
    ) -> None:
        self.base_xp = base_xp
        self.multiplier = multiplier
        self.anti_farming = anti_farming or AntiFarmingGuard()

    def calculate_level_from_xp(self, total_xp: int) -> int:
        """
        Derive level from cumulative total XP.
        Level starts at 1.
        Level L requires cumulative XP:
          L=1: 0
          L=2: base_xp
          L=3: base_xp + base_xp * (2 ** multiplier), etc.
        """
        if total_xp <= 0:
            return 1

        level = 1
        xp_needed = 0
        while True:
            step = int(self.base_xp * (level**self.multiplier))
            if xp_needed + step > total_xp:
                return level
            xp_needed += step
            level += 1
            if level > 1000:  # Safety guard
                return 1000

    def xp_for_next_level(self, current_level: int) -> int:
        """Calculate XP required to advance from current_level to next."""
        return int(self.base_xp * (current_level**self.multiplier))

    async def process_chat_message(
        self,
        session: AsyncSession,
        creator_id: str,
        viewer_channel_id: str,
        display_name: str,
        message_text: str,
        base_reward: int = 15,
    ) -> tuple[bool, str, int, bool]:
        """
        Process chat message for XP reward.
        Returns (awarded: bool, reason: str, total_xp: int, leveled_up: bool).
        """
        repo = EngagementRepository(session)
        profile = await repo.get_or_create(creator_id, viewer_channel_id, display_name)

        # 1. Update message counter
        await repo.increment_message(profile)

        # 2. Content quality gate
        meaningful, reason = self.anti_farming.is_message_meaningful(message_text)
        if not meaningful:
            return False, reason, profile.total_xp, False

        # 3. Anti-farming velocity gate
        can_award, reason = self.anti_farming.can_award_xp(
            creator_id, viewer_channel_id, base_reward
        )
        if not can_award:
            return False, reason, profile.total_xp, False

        # 4. Award XP and check level progression
        old_level = profile.level
        new_total_xp = profile.total_xp + base_reward
        new_level = self.calculate_level_from_xp(new_total_xp)
        leveled_up = new_level > old_level

        await repo.award_xp(profile, base_reward, new_level)
        self.anti_farming.record_award(creator_id, viewer_channel_id, base_reward)

        if leveled_up:
            logger.info(
                f"🎉 LEVEL UP! Viewer {display_name} ({viewer_channel_id}) reached Level {new_level} on creator {creator_id}!"
            )

        return True, "XP_AWARDED", new_total_xp, leveled_up

"""Feature flag evaluation and management service with cascading resolution and auditing."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.feature_flag import FeatureFlag
from app.db.repositories.audit_repo import AuditRepository

logger = get_logger("app.services.feature_flags")

# Default values for critical operational kill switches
DEFAULT_FLAGS: dict[str, bool] = {
    "HONNEY": True,
    "AI_MODERATION": True,
    "OPENROUTER": True,
    "ECONOMY": True,
    "MINIGAMES": True,
    "DISCORD_ALERTS": True,
    "WEBSUB": True,
    "AUTO_RECONNECT": True,
}


class FeatureFlagService:
    """
    Cascading feature flag evaluator:
    1. Stream override (if specified)
    2. Creator override (creator_id matching)
    3. Environment override (matching settings.APP_ENV)
    4. Global override (environment='all', creator_id=None)
    5. Hardcoded conservative default
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.audit_repo = AuditRepository(session)

    async def is_enabled(
        self,
        flag_key: str,
        creator_id: str | None = None,
        default: bool | None = None,
    ) -> bool:
        """Evaluate whether a feature flag is enabled for the current context."""
        key_upper = flag_key.upper()

        # Query all active flags for this key
        stmt = select(FeatureFlag).where(FeatureFlag.key == key_upper)
        res = await self.session.execute(stmt)
        flags = res.scalars().all()

        if not flags:
            return default if default is not None else DEFAULT_FLAGS.get(key_upper, True)

        # 1. Creator-specific override for current environment or all
        if creator_id:
            for f in flags:
                if f.creator_id == creator_id and f.environment in (
                    self.settings.APP_ENV,
                    "all",
                ):
                    return f.enabled

        # 2. Environment-specific override (e.g. production vs development)
        for f in flags:
            if f.creator_id is None and f.environment == self.settings.APP_ENV:
                return f.enabled

        # 3. Global override
        for f in flags:
            if f.creator_id is None and f.environment == "all":
                return f.enabled

        return default if default is not None else DEFAULT_FLAGS.get(key_upper, True)

    async def set_flag(
        self,
        key: str,
        enabled: bool,
        creator_id: str | None = None,
        environment: str = "all",
        actor_id: str = "SYSTEM",
        reason: str | None = None,
    ) -> FeatureFlag:
        """Set or update a feature flag with an immutable audit log entry."""
        key_upper = key.upper()
        stmt = select(FeatureFlag).where(
            FeatureFlag.key == key_upper,
            FeatureFlag.creator_id == creator_id,
            FeatureFlag.environment == environment,
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        old_state = existing.enabled if existing else None
        if existing:
            existing.enabled = enabled
            flag_obj = existing
        else:
            flag_obj = FeatureFlag(
                key=key_upper,
                enabled=enabled,
                creator_id=creator_id,
                environment=environment,
                description=reason or f"Feature flag {key_upper}",
            )
            self.session.add(flag_obj)

        await self.session.flush()

        # Audit the flag modification
        await self.audit_repo.log_event(
            event_type="feature_flag.update",
            actor_type="ADMIN",
            actor_id=actor_id,
            creator_id=creator_id,
            payload={
                "key": key_upper,
                "previous_state": old_state,
                "new_state": enabled,
                "environment": environment,
                "reason": reason,
            },
        )
        logger.info(
            f"FeatureFlag '{key_upper}' set to {enabled} (creator: {creator_id}, env: {environment}) by {actor_id}"
        )
        return flag_obj

    async def list_flags(self) -> list[dict[str, Any]]:
        """List all configured feature flags with effective defaults."""
        stmt = select(FeatureFlag).order_by(FeatureFlag.key)
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            {
                "id": r.id,
                "key": r.key,
                "enabled": r.enabled,
                "creator_id": r.creator_id,
                "environment": r.environment,
                "description": r.description,
            }
            for r in rows
        ]

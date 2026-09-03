"""Repository for CreatorAISettings records."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator_ai_settings import CreatorAISettings
from app.db.repositories.base import BaseRepository


class CreatorAISettingsRepository(BaseRepository[CreatorAISettings]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CreatorAISettings, session)

    async def get_by_creator_id(self, creator_id: str) -> CreatorAISettings | None:
        """Fetch AI settings for creator."""
        result = await self.session.execute(
            select(CreatorAISettings).where(CreatorAISettings.creator_id == creator_id)
        )
        return result.scalars().first()

    async def get_or_create(self, creator_id: str) -> CreatorAISettings:
        """Fetch existing AI settings or initialize default settings for creator."""
        settings = await self.get_by_creator_id(creator_id)
        if not settings:
            settings = CreatorAISettings(
                creator_id=creator_id,
                ai_enabled=True,
                persona_type="CO_HOST",
                moderation_strictness="BALANCED",
                moderation_mode="ACTIVE",
                auto_moderation_enabled=True,
                hitl_enabled=True,
                ai_reply_enabled=True,
                greeting_enabled=True,
                farewell_enabled=True,
                quiet_mode_enabled=True,
            )
            self.session.add(settings)
            await self.session.flush()
        return settings

    async def update_settings(self, creator_id: str, **updates: Any) -> CreatorAISettings:
        """Update creator AI settings attributes."""
        settings = await self.get_or_create(creator_id)
        for key, value in updates.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        await self.session.flush()
        return settings

"""Repository for creator Discord configuration."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.discord_config import CreatorDiscordConfig


class DiscordConfigRepository:
    """Repository managing creator-specific Discord channel routing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_creator_id(self, creator_id: str) -> CreatorDiscordConfig | None:
        stmt = select(CreatorDiscordConfig).where(CreatorDiscordConfig.creator_id == creator_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_config(
        self,
        creator_id: str,
        log_channel_id: str | None = None,
        alert_channel_id: str | None = None,
        summary_channel_id: str | None = None,
        enabled: bool = True,
    ) -> CreatorDiscordConfig:
        config = await self.get_by_creator_id(creator_id)
        if config:
            if log_channel_id is not None:
                config.log_channel_id = log_channel_id
            if alert_channel_id is not None:
                config.alert_channel_id = alert_channel_id
            if summary_channel_id is not None:
                config.summary_channel_id = summary_channel_id
            config.enabled = enabled
        else:
            config = CreatorDiscordConfig(
                creator_id=creator_id,
                log_channel_id=log_channel_id,
                alert_channel_id=alert_channel_id,
                summary_channel_id=summary_channel_id,
                enabled=enabled,
            )
            self.session.add(config)

        await self.session.flush()
        return config

    async def list_all_active(self) -> list[CreatorDiscordConfig]:
        stmt = select(CreatorDiscordConfig).where(CreatorDiscordConfig.enabled.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

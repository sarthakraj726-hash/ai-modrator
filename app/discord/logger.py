"""Discord logging abstraction with creator channel routing and developer alerts."""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.discord.logger")


class DiscordMessagePayload(BaseModel):
    channel_id: str
    content: str
    embeds: list[dict[str, Any]] = Field(default_factory=list)
    mention_dev: bool = False


class DiscordLogger:
    """
    Discord logging abstraction.
    Routes creator-specific logs to creator channels and critical alerts to developer channels.
    """

    def __init__(self, bot_token: str | None = None, dev_channel_id: str | None = None):
        settings = get_settings()
        self.bot_token = bot_token or settings.DISCORD_BOT_TOKEN
        self.dev_channel_id = dev_channel_id or settings.DISCORD_DEV_CHANNEL_ID
        self._creator_channels: dict[str, str] = {}  # creator_id -> discord_channel_id

    def register_creator_channel(self, creator_id: str, discord_channel_id: str) -> None:
        """Map a creator's YouTube channel to their designated Discord log channel."""
        self._creator_channels[creator_id] = discord_channel_id
        logger.info(f"Mapped creator {creator_id} to Discord log channel {discord_channel_id}")

    async def log_creator_event(self, creator_id: str, message: str, title: str = "Stream Event") -> bool:
        """Send a creator log notification to creator's designated Discord channel."""
        channel_id = self._creator_channels.get(creator_id)
        if not channel_id:
            logger.debug(f"No Discord log channel mapped for creator {creator_id}")
            return False

        return await self._send_message(
            DiscordMessagePayload(
                channel_id=channel_id,
                content=f"**[{title}]** {message}",
            )
        )

    async def send_developer_alert(self, message: str, severity: str = "ERROR", mention: bool = False) -> bool:
        """Send high-priority alert to developer Discord channel."""
        if not self.dev_channel_id:
            logger.debug("No Discord dev channel ID configured")
            return False

        content = f"🚨 **[SYSTEM {severity.upper()}]** {message}"
        if mention:
            content = f"@everyone {content}"

        return await self._send_message(
            DiscordMessagePayload(
                channel_id=self.dev_channel_id,
                content=content,
                mention_dev=mention,
            )
        )

    async def _send_message(self, payload: DiscordMessagePayload) -> bool:
        """Internal dispatch over Discord HTTP webhook/bot API or simulated logger."""
        if not self.bot_token or not payload.channel_id:
            logger.info(f"[DiscordLog simulated -> channel:{payload.channel_id}]: {payload.content}")
            return True

        # When bot token is configured, post to Discord API
        try:
            url = f"https://discord.com/api/v10/channels/{payload.channel_id}/messages"
            headers = {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, headers=headers, json={"content": payload.content})
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Failed to deliver Discord message: {e}")
            return False


_global_discord_logger: DiscordLogger | None = None


def get_discord_logger() -> DiscordLogger:
    """Return singleton DiscordLogger."""
    global _global_discord_logger
    if _global_discord_logger is None:
        _global_discord_logger = DiscordLogger()
    return _global_discord_logger

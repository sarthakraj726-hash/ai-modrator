"""Unit tests for DiscordLogger abstraction."""

import pytest

from app.discord.logger import DiscordLogger


@pytest.mark.asyncio
async def test_discord_logger_routing():
    logger = DiscordLogger(bot_token="", dev_channel_id="dev-channel-999")
    logger.register_creator_channel("creator-1", "channel-111")

    # Creator event
    c_res = await logger.log_creator_event("creator-1", "Stream started", title="Live")
    assert c_res is True

    # Developer alert
    d_res = await logger.send_developer_alert("High CPU usage", severity="WARNING", mention=False)
    assert d_res is True

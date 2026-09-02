"""WebSub subscription lifecycle manager."""

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.db.models.websub_subscription import WebSubStatus, WebSubSubscription
from app.db.repositories.websub_repo import WebSubRepository

logger = get_logger("app.youtube.websub.manager")

PUBSUBHUBBUB_HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"
YOUTUBE_TOPIC_BASE = "https://www.youtube.com/xml/feeds/videos.xml?channel_id="


class WebSubSubscriptionManager:
    """Manages subscribing, renewing, and unsubscribing creator channels to/from Google WebSub hub."""

    def __init__(self, hub_url: str = PUBSUBHUBBUB_HUB_URL) -> None:
        self.hub_url = hub_url
        self.settings = get_settings()

    def get_topic_url(self, channel_id: str) -> str:
        """Construct canonical YouTube channel topic URL."""
        return f"{YOUTUBE_TOPIC_BASE}{channel_id}"

    async def subscribe_channel(
        self,
        creator_id: str,
        channel_id: str,
        callback_url: str,
        db_session: AsyncSession,
        lease_seconds: int = 864000,
    ) -> WebSubSubscription:
        """
        Send subscribe request to Google PubSubHubbub hub and record subscription state.
        """
        topic_url = self.get_topic_url(channel_id)
        repo = WebSubRepository(db_session)
        sub = await repo.get_by_channel_id(channel_id)

        now = datetime.now(UTC)
        if not sub:
            sub = WebSubSubscription(
                creator_id=creator_id,
                channel_id=channel_id,
                topic_url=topic_url,
                callback_url=callback_url,
                status=WebSubStatus.PENDING.value,
                lease_seconds=lease_seconds,
                last_subscribed_at=now,
            )
            sub = await repo.create(sub)
        else:
            sub.status = WebSubStatus.PENDING.value
            sub.callback_url = callback_url
            sub.lease_seconds = lease_seconds
            sub.last_subscribed_at = now
            await db_session.flush()

        # Send asynchronous request to Google Hub
        payload = {
            "hub.callback": callback_url,
            "hub.mode": "subscribe",
            "hub.topic": topic_url,
            "hub.verify": "async",
            "hub.lease_seconds": str(lease_seconds),
        }

        logger.info(
            f"Sending WebSub subscribe request for channel '{channel_id}' to {self.hub_url}"
        )
        http_timeout = 0.5 if self.settings.is_testing else 10.0
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(self.hub_url, data=payload)
                if response.status_code not in (200, 202, 204):
                    err_msg = f"Hub returned status {response.status_code}: {response.text}"
                    logger.error(f"WebSub subscription failed: {err_msg}")
                    await repo.update_status(sub.id, status=WebSubStatus.FAILED, last_error=err_msg)
                    raise ExternalServiceError("WebSubHub", err_msg)

                logger.info(f"WebSub subscribe request accepted by hub for channel '{channel_id}'.")
                return sub

        except httpx.RequestError as e:
            err_msg = f"Network error contacting WebSub hub: {e}"
            logger.error(err_msg)
            await repo.update_status(sub.id, status=WebSubStatus.FAILED, last_error=err_msg)
            raise ExternalServiceError("WebSubHub", err_msg) from e

    async def unsubscribe_channel(
        self,
        channel_id: str,
        callback_url: str,
        db_session: AsyncSession,
    ) -> bool:
        """Send unsubscribe request to Google PubSubHubbub hub."""
        topic_url = self.get_topic_url(channel_id)
        repo = WebSubRepository(db_session)
        sub = await repo.get_by_channel_id(channel_id)

        payload = {
            "hub.callback": callback_url,
            "hub.mode": "unsubscribe",
            "hub.topic": topic_url,
            "hub.verify": "async",
        }

        logger.info(f"Sending WebSub unsubscribe request for channel '{channel_id}'")
        http_timeout = 0.5 if self.settings.is_testing else 10.0
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(self.hub_url, data=payload)
                if sub:
                    await repo.update_status(sub.id, status=WebSubStatus.DISABLED)
                return response.status_code in (200, 202, 204)
        except Exception as e:
            logger.warning(f"Error unsubscribing channel '{channel_id}': {e}")
            if sub:
                await repo.update_status(sub.id, status=WebSubStatus.FAILED, last_error=str(e))
            return False


_global_websub_manager: WebSubSubscriptionManager | None = None


def get_websub_manager() -> WebSubSubscriptionManager:
    """Return singleton WebSubSubscriptionManager."""
    global _global_websub_manager
    if _global_websub_manager is None:
        _global_websub_manager = WebSubSubscriptionManager()
    return _global_websub_manager

"""Repository for WebSub subscriptions."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.websub_subscription import WebSubStatus, WebSubSubscription
from app.db.repositories.base import BaseRepository


class WebSubRepository(BaseRepository[WebSubSubscription]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WebSubSubscription, session)

    async def get_by_creator_id(self, creator_id: str) -> list[WebSubSubscription]:
        """Fetch all subscriptions for a creator."""
        result = await self.session.execute(
            select(WebSubSubscription).where(WebSubSubscription.creator_id == creator_id)
        )
        return list(result.scalars().all())

    async def get_by_channel_id(self, channel_id: str) -> WebSubSubscription | None:
        """Fetch subscription by YouTube channel ID."""
        result = await self.session.execute(
            select(WebSubSubscription).where(WebSubSubscription.channel_id == channel_id)
        )
        return result.scalars().first()

    async def get_by_topic_url(self, topic_url: str) -> WebSubSubscription | None:
        """Fetch subscription by topic URL."""
        result = await self.session.execute(
            select(WebSubSubscription).where(WebSubSubscription.topic_url == topic_url)
        )
        return result.scalars().first()

    async def list_expiring_soon(self, before_time: datetime) -> list[WebSubSubscription]:
        """Fetch active subscriptions that expire before specified time."""
        result = await self.session.execute(
            select(WebSubSubscription).where(
                WebSubSubscription.status == WebSubStatus.ACTIVE.value,
                WebSubSubscription.lease_expires_at <= before_time,
            )
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        subscription_id: str,
        status: WebSubStatus,
        lease_seconds: int | None = None,
        lease_expires_at: datetime | None = None,
        last_error: str | None = None,
    ) -> WebSubSubscription | None:
        """Update subscription status and lease information."""
        sub = await self.get_by_id(subscription_id)
        if not sub:
            return None
        sub.status = status.value
        if lease_seconds is not None:
            sub.lease_seconds = lease_seconds
        if lease_expires_at is not None:
            sub.lease_expires_at = lease_expires_at
        if status == WebSubStatus.ACTIVE:
            sub.last_verified_at = datetime.now()
            sub.failure_count = 0
            sub.last_error = None
        elif status == WebSubStatus.FAILED:
            sub.failure_count += 1
            sub.last_error = last_error
        await self.session.flush()
        return sub

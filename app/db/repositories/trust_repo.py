"""Repository for ViewerTrustProfile records."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.viewer_trust import ViewerTrustProfile
from app.db.repositories.base import BaseRepository


class ViewerTrustRepository(BaseRepository[ViewerTrustProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ViewerTrustProfile, session)

    async def get_or_create(
        self,
        creator_id: str,
        viewer_channel_id: str,
        display_name: str,
    ) -> ViewerTrustProfile:
        """Fetch existing trust profile for creator/viewer or initialize new profile."""
        result = await self.session.execute(
            select(ViewerTrustProfile).where(
                ViewerTrustProfile.creator_id == creator_id,
                ViewerTrustProfile.viewer_channel_id == viewer_channel_id,
            )
        )
        profile = result.scalars().first()
        if not profile:
            now = datetime.now(UTC)
            profile = ViewerTrustProfile(
                creator_id=creator_id,
                viewer_channel_id=viewer_channel_id,
                display_name=display_name,
                trust_score=50,
                first_seen_at=now,
                last_seen_at=now,
                messages_seen=1,
            )
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def record_interaction(
        self,
        creator_id: str,
        viewer_channel_id: str,
        display_name: str,
        positive_delta: int = 1,
    ) -> ViewerTrustProfile:
        """Record normal chat interaction and increment positive points (up to max 100)."""
        profile = await self.get_or_create(creator_id, viewer_channel_id, display_name)
        profile.display_name = display_name
        profile.messages_seen += 1
        profile.positive_interactions += 1
        profile.last_seen_at = datetime.now(UTC)
        # Gradually increase trust score up to 100
        profile.trust_score = min(100, profile.trust_score + positive_delta)
        await self.session.flush()
        return profile

    async def record_violation(
        self,
        creator_id: str,
        viewer_channel_id: str,
        display_name: str,
        action_type: str,
        penalty: int = 15,
    ) -> ViewerTrustProfile:
        """Record confirmed violation and decrement trust score."""
        profile = await self.get_or_create(creator_id, viewer_channel_id, display_name)
        profile.last_seen_at = datetime.now(UTC)
        profile.trust_score = max(0, profile.trust_score - penalty)

        if action_type == "WARN":
            profile.warning_count += 1
        elif action_type == "TIMEOUT":
            profile.timeout_count += 1
        elif action_type == "HIDE":
            profile.hide_count += 1

        await self.session.flush()
        return profile

    async def update_last_greeting(
        self,
        creator_id: str,
        viewer_channel_id: str,
    ) -> None:
        """Record timestamp of recent greeting to enforce greeting cooldown."""
        result = await self.session.execute(
            select(ViewerTrustProfile).where(
                ViewerTrustProfile.creator_id == creator_id,
                ViewerTrustProfile.viewer_channel_id == viewer_channel_id,
            )
        )
        profile = result.scalars().first()
        if profile:
            profile.last_greeting_at = datetime.now(UTC)
            await self.session.flush()

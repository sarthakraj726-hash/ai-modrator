"""Repository for MiniGameSession entities."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.mini_game import MiniGameSession


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_game(
        self, creator_id: str, stream_session_id: str
    ) -> MiniGameSession | None:
        """Find currently active mini-game for a creator's stream session."""
        now = datetime.now(UTC)
        stmt = (
            select(MiniGameSession)
            .where(
                MiniGameSession.creator_id == creator_id,
                MiniGameSession.stream_session_id == stream_session_id,
                MiniGameSession.state == "ACTIVE",
                MiniGameSession.expires_at > now,
            )
            .order_by(MiniGameSession.started_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_game(
        self,
        creator_id: str,
        stream_session_id: str,
        game_type: str,
        prompt_text: str,
        solution_data: dict[str, Any],
        reward_xp: int = 50,
        reward_coins: int = 25,
        expires_at: datetime | None = None,
    ) -> MiniGameSession:
        """Create new active game session."""
        session = MiniGameSession(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            game_type=game_type,
            prompt_text=prompt_text,
            solution_data=solution_data,
            reward_xp=reward_xp,
            reward_coins=reward_coins,
            expires_at=expires_at or datetime.now(UTC),
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def complete_game(
        self, game_id: str, winner_channel_id: str, winner_display_name: str
    ) -> MiniGameSession | None:
        """Mark game as completed with the winning viewer."""
        stmt = select(MiniGameSession).where(MiniGameSession.id == game_id)
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        if game and game.state == "ACTIVE":
            game.state = "COMPLETED"
            game.winner_channel_id = winner_channel_id
            game.winner_display_name = winner_display_name
            await self.session.flush()
        return game

    async def expire_game(self, game_id: str) -> MiniGameSession | None:
        """Mark game as expired without winner."""
        stmt = select(MiniGameSession).where(MiniGameSession.id == game_id)
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        if game and game.state == "ACTIVE":
            game.state = "EXPIRED"
            await self.session.flush()
        return game

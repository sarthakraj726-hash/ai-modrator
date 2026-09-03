"""Unit tests for deterministic live chat mini-game engine."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.db.repositories.engagement_repo import EngagementRepository
from app.economy.ledger import EconomyService
from app.games.engine import MiniGameEngine


@pytest.fixture
async def game_stream(db_session: AsyncSession) -> tuple[Creator, StreamSession]:
    creator = Creator(
        id="c-game-1",
        youtube_channel_id="UC_game_1",
        channel_name="Game Streamer",
    )
    db_session.add(creator)
    stream = StreamSession(
        id="s-game-1",
        creator_id="c-game-1",
        youtube_video_id="vid_game_1",
        youtube_live_chat_id="chat_game_1",
    )
    db_session.add(stream)
    await db_session.flush()
    return creator, stream


@pytest.mark.asyncio
async def test_mini_game_lifecycle_and_winner_reward(
    db_session: AsyncSession, game_stream: tuple[Creator, StreamSession]
):
    creator, stream = game_stream
    engine = MiniGameEngine()

    # 1. Start Reaction Game
    success, prompt, session_obj = await engine.start_game(
        session=db_session,
        creator_id=creator.id,
        stream_session_id=stream.id,
        game_type="REACTION",
    )
    assert success is True
    assert "REACTION SPEED" in prompt
    assert session_obj.state == "ACTIVE"

    target = session_obj.solution_data["answer"]

    # 2. Incorrect chat guess
    won, announcement = await engine.evaluate_chat_guess(
        session=db_session,
        creator_id=creator.id,
        stream_session_id=stream.id,
        viewer_channel_id="v_loser",
        viewer_display_name="SlowPoke",
        chat_text="Wrong text completely",
    )
    assert won is False
    assert announcement is None

    # 3. Correct chat guess
    won, announcement = await engine.evaluate_chat_guess(
        session=db_session,
        creator_id=creator.id,
        stream_session_id=stream.id,
        viewer_channel_id="v_winner",
        viewer_display_name="FastFingers",
        chat_text=f"Hey everyone {target} let's go!",
    )
    assert won is True
    assert "won the REACTION game" in announcement
    assert "+50 XP, +25 Coins" in announcement

    # 4. Verify winner received rewards
    economy = EconomyService(db_session)
    coins = await economy.get_balance(creator.id, "v_winner")
    assert coins == 25

    eng_repo = EngagementRepository(db_session)
    profile = await eng_repo.get_by_viewer(creator.id, "v_winner")
    assert profile.total_xp == 50
    assert profile.games_played == 1
    assert profile.games_won == 1

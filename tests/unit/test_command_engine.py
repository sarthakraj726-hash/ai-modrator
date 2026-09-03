"""Unit tests for CommandEngine, argument parsing, RBAC, and cooldowns."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.engine import ProductionCommandEngine
from app.commands.models import CommandExecutionContext
from app.core.rbac import Role
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.db.repositories.command_repo import CommandRepository
from app.youtube.models import YouTubeAuthor


@pytest.mark.asyncio
async def test_command_parser_and_prefix():
    engine = ProductionCommandEngine()

    assert engine.is_command("!help") is True
    assert engine.is_command("!level") is True
    assert engine.is_command("!uk add test hello") is True
    assert engine.is_command("Hello world") is False
    assert engine.is_command("!!double") is False
    assert engine.is_command("!") is False

    cmd, args = engine.parse_command("!buy VIP badge 50")
    assert cmd == "buy"
    assert args == ["VIP", "badge", "50"]


@pytest.mark.asyncio
async def test_builtin_command_execution(db_session: AsyncSession):
    creator = Creator(
        id="c-eng-1",
        youtube_channel_id="UC_test_c1",
        channel_name="Test Creator 1",
    )
    db_session.add(creator)
    session_obj = StreamSession(
        id="s-eng-1",
        creator_id="c-eng-1",
        youtube_video_id="vid_123",
        youtube_live_chat_id="chat_123",
    )
    db_session.add(session_obj)
    await db_session.flush()

    engine = ProductionCommandEngine()
    author = YouTubeAuthor(
        channel_id="viewer_bob",
        display_name="BobTheViewer",
        is_chat_owner=False,
        is_chat_moderator=False,
    )

    ctx = CommandExecutionContext(
        command_name="help",
        args=[],
        raw_text="!help",
        creator_id="c-eng-1",
        stream_session_id="s-eng-1",
        author=author,
        author_role=Role.VIEWER,
    )

    result = await engine.execute_command(ctx, db_session)
    assert result.success is True
    assert "Commands:" in result.response_message
    assert len(result.response_message) <= 200


@pytest.mark.asyncio
async def test_command_cooldown_throttling(db_session: AsyncSession):
    engine = ProductionCommandEngine()
    author = YouTubeAuthor(
        channel_id="viewer_speedy",
        display_name="Speedy",
        is_chat_owner=False,
        is_chat_moderator=False,
    )

    ctx = CommandExecutionContext(
        command_name="rules",
        args=[],
        raw_text="!rules",
        creator_id="c-throttle-1",
        stream_session_id="s-throttle-1",
        author=author,
        author_role=Role.VIEWER,
    )

    # First call: succeeds
    res1 = await engine.execute_command(ctx, db_session)
    assert res1.success is True

    # Immediate second call: throttled by cooldown
    res2 = await engine.execute_command(ctx, db_session)
    assert res2.success is False
    assert res2.error_message == "COOLDOWN_ACTIVE"
    assert "cooldown" in res2.response_message.lower()


@pytest.mark.asyncio
async def test_custom_command_execution(db_session: AsyncSession):
    creator = Creator(
        id="c-custom-1",
        youtube_channel_id="UC_custom_1",
        channel_name="Custom Creator",
    )
    db_session.add(creator)
    await db_session.flush()

    repo = CommandRepository(db_session)
    await repo.create_command(
        creator_id="c-custom-1",
        name="instagram",
        response="Follow our Insta at https://instagram.com/test! Shoutout to {user}!",
        min_role=Role.VIEWER,
    )
    await db_session.flush()

    engine = ProductionCommandEngine()
    author = YouTubeAuthor(
        channel_id="viewer_alice",
        display_name="Alice",
    )

    ctx = CommandExecutionContext(
        command_name="instagram",
        args=[],
        raw_text="!instagram",
        creator_id="c-custom-1",
        stream_session_id="s-custom-1",
        author=author,
        author_role=Role.VIEWER,
    )

    result = await engine.execute_command(ctx, db_session)
    assert result.success is True
    assert "@Alice" in result.response_message
    assert "instagram.com/test" in result.response_message

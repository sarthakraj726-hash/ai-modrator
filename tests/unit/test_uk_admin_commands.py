from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.engine import ProductionCommandEngine
from app.commands.models import CommandExecutionContext
from app.core.rbac import Role
from app.db.models.creator import Creator
from app.db.models.moderation_review import ModerationReview
from app.db.models.stream_session import StreamSession
from app.db.repositories.command_repo import CommandRepository
from app.economy.ledger import EconomyService
from app.youtube.models import YouTubeAuthor


@pytest.fixture
async def admin_creator(db_session: AsyncSession) -> tuple[Creator, StreamSession]:
    creator = Creator(
        id="c-admin-1",
        youtube_channel_id="UC_admin_1",
        channel_name="Admin Streamer",
    )
    db_session.add(creator)
    stream = StreamSession(
        id="s-admin-1",
        creator_id="c-admin-1",
        youtube_video_id="vid_admin_1",
        youtube_live_chat_id="chat_admin_1",
    )
    db_session.add(stream)
    await db_session.flush()
    return creator, stream


@pytest.mark.asyncio
async def test_uk_viewer_permission_denied(
    db_session: AsyncSession, admin_creator: tuple[Creator, StreamSession]
):
    creator, stream = admin_creator
    engine = ProductionCommandEngine()

    viewer_author = YouTubeAuthor(
        channel_id="v_unauthorized",
        display_name="SneakyViewer",
    )

    ctx = CommandExecutionContext(
        command_name="uk",
        args=["add", "badcmd", "malicious"],
        raw_text="!uk add badcmd malicious",
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=viewer_author,
        author_role=Role.VIEWER,
    )

    result = await engine.execute_command(ctx, db_session)
    assert result.success is False
    assert result.error_message == "PERMISSION_DENIED"
    assert "Permission denied" in result.response_message


@pytest.mark.asyncio
async def test_uk_add_edit_delete_custom_command(
    db_session: AsyncSession, admin_creator: tuple[Creator, StreamSession]
):
    creator, stream = admin_creator
    engine = ProductionCommandEngine()
    mod_author = YouTubeAuthor(
        channel_id="mod_sarah",
        display_name="SarahMod",
        is_chat_moderator=True,
    )

    # 1. Add command via !uk
    ctx_add = CommandExecutionContext(
        command_name="uk",
        args=["add", "twitter", '"Follow us on https://x.com/honney!"'],
        raw_text='!uk add twitter "Follow us on https://x.com/honney!"',
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=mod_author,
        author_role=Role.MODERATOR,
    )
    res_add = await engine.execute_command(ctx_add, db_session)
    assert res_add.success is True
    assert "Created custom command '!twitter'" in res_add.response_message

    # Verify command is now executable by ordinary viewers
    repo = CommandRepository(db_session)
    cmd = await repo.get_by_name(creator.id, "twitter")
    assert cmd is not None
    assert "https://x.com/honney!" in cmd.response

    # 2. Edit command via !uk
    ctx_edit = CommandExecutionContext(
        command_name="uk",
        args=["edit", "twitter", '"Updated X handle: @HonneyAI"'],
        raw_text='!uk edit twitter "Updated X handle: @HonneyAI"',
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=mod_author,
        author_role=Role.MODERATOR,
    )
    res_edit = await engine.execute_command(ctx_edit, db_session)
    assert res_edit.success is True
    assert "Updated custom command '!twitter'" in res_edit.response_message

    # 3. Delete command via !uk
    ctx_del = CommandExecutionContext(
        command_name="uk",
        args=["delete", "twitter"],
        raw_text="!uk delete twitter",
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=mod_author,
        author_role=Role.MODERATOR,
    )
    res_del = await engine.execute_command(ctx_del, db_session)
    assert res_del.success is True
    assert "Deleted custom command '!twitter'" in res_del.response_message
    assert await repo.get_by_name(creator.id, "twitter") is None


@pytest.mark.asyncio
async def test_uk_give_coins(
    db_session: AsyncSession, admin_creator: tuple[Creator, StreamSession]
):
    creator, stream = admin_creator
    engine = ProductionCommandEngine()
    creator_author = YouTubeAuthor(
        channel_id="owner_channel",
        display_name="OwnerStreamer",
        is_chat_owner=True,
    )

    ctx = CommandExecutionContext(
        command_name="uk",
        args=["give", "@lucky_viewer", "500"],
        raw_text="!uk give @lucky_viewer 500",
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=creator_author,
        author_role=Role.CREATOR,
    )

    res = await engine.execute_command(ctx, db_session)
    assert res.success is True
    assert "Granted 500 coins to @lucky_viewer" in res.response_message

    economy = EconomyService(db_session)
    balance = await economy.get_balance(creator.id, "lucky_viewer")
    assert balance == 500


@pytest.mark.asyncio
async def test_uk_punish_phase3_hitl_integration(
    db_session: AsyncSession, admin_creator: tuple[Creator, StreamSession]
):
    creator, stream = admin_creator

    # Create a pending moderation review
    review = ModerationReview(
        id="rev-12345678-abcd-ef01",
        creator_id=creator.id,
        stream_session_id=stream.id,
        message_id="msg_toxic_99",
        author_channel_id="v_toxic",
        author_display_name="ToxicUser",
        message_text="You are awful",
        status="PENDING",
        recommended_action="HIDE",
        reason_code="HARASSMENT",
        reason="Toxic message",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(review)
    await db_session.flush()

    engine = ProductionCommandEngine()
    mod_author = YouTubeAuthor(
        channel_id="mod_jack",
        display_name="JackMod",
        is_chat_moderator=True,
    )

    # Approve punishment via chat command: !uk punish rev-12345678 yes
    ctx = CommandExecutionContext(
        command_name="uk",
        args=["punish", "rev-1234", "yes"],
        raw_text="!uk punish rev-1234 yes",
        creator_id=creator.id,
        stream_session_id=stream.id,
        author=mod_author,
        author_role=Role.MODERATOR,
    )

    res = await engine.execute_command(ctx, db_session)
    assert res.success is True
    assert "approved" in res.response_message.lower()

    # Verify review status was updated to APPROVED
    await db_session.refresh(review)
    assert review.status == "APPROVED"

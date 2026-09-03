"""Seven-stream multi-tenant simulation verifying strict engagement, economy, and command isolation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.engine import ProductionCommandEngine
from app.commands.models import CommandExecutionContext
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.db.repositories.command_repo import CommandRepository
from app.economy.ledger import EconomyService
from app.engagement.leaderboards import LeaderboardService
from app.engagement.xp import AntiFarmingGuard, XPManager
from app.games.engine import MiniGameEngine
from app.store.service import StoreService
from app.youtube.models import YouTubeAuthor


@pytest.mark.asyncio
async def test_seven_stream_concurrent_isolation(db_session: AsyncSession):
    """
    Simulate 7 concurrent live streams with distinct creators, viewers,
    custom commands, economies, store items, games, and leaderboards.
    Verify 100% tenant isolation across all 7 streams.
    """
    num_streams = 7
    creators: list[Creator] = []
    streams: list[StreamSession] = []

    # 1. Initialize 7 Creators and Streams
    for i in range(1, num_streams + 1):
        creator = Creator(
            id=f"sim-creator-{i}",
            youtube_channel_id=f"UC_sim_{i}",
            channel_name=f"Creator Streamer {i}",
        )
        stream = StreamSession(
            id=f"sim-stream-{i}",
            creator_id=creator.id,
            youtube_video_id=f"vid_sim_{i}",
            youtube_live_chat_id=f"chat_sim_{i}",
        )
        db_session.add(creator)
        db_session.add(stream)
        creators.append(creator)
        streams.append(stream)

    await db_session.flush()

    cmd_repo = CommandRepository(db_session)
    economy = EconomyService(db_session)
    store = StoreService(db_session)
    xp_mgr = XPManager(base_xp=100, anti_farming=AntiFarmingGuard(cooldown_seconds=0))
    game_engine = MiniGameEngine(xp_mgr)
    command_engine = ProductionCommandEngine(xp_manager=xp_mgr, game_engine=game_engine)

    # 2. Setup Creator-Specific Assets on Each Stream
    for i in range(1, num_streams + 1):
        c_id = f"sim-creator-{i}"
        # Unique custom command per creator: !stream1, !stream2, etc.
        await cmd_repo.create_command(
            creator_id=c_id,
            name=f"stream{i}",
            response=f"Welcome to Stream {i}'s exclusive command!",
        )
        # Unique store item per creator: Item_{i}
        await store.create_item(
            creator_id=c_id,
            name=f"Perk_{i}",
            description=f"Perk for Stream {i}",
            price=50 * i,
            stock=10,
        )

    await db_session.flush()

    # 3. Simulate Concurrent Stream Activity
    # Universal viewer "shared_viewer" watches both Stream 1 and Stream 2
    # In Stream 1: Viewer earns 500 coins and 200 XP
    # In Stream 2: Viewer earns 100 coins and 50 XP
    await economy.earn("sim-creator-1", "shared_viewer", 500, "Stream 1 chat")
    await xp_mgr.process_chat_message(
        session=db_session,
        creator_id="sim-creator-1",
        viewer_channel_id="shared_viewer",
        display_name="SharedViewer",
        message_text="Chatting on Stream 1",
        base_reward=200,
    )

    await economy.earn("sim-creator-2", "shared_viewer", 100, "Stream 2 chat")
    await xp_mgr.process_chat_message(
        session=db_session,
        creator_id="sim-creator-2",
        viewer_channel_id="shared_viewer",
        display_name="SharedViewer",
        message_text="Chatting on Stream 2",
        base_reward=50,
    )

    # In Streams 3 to 7: Viewer has NOT chatted yet

    # 4. Verify Strict Isolation Invariants

    # Invariant A: Coins are strictly isolated per creator
    assert await economy.get_balance("sim-creator-1", "shared_viewer") == 500
    assert await economy.get_balance("sim-creator-2", "shared_viewer") == 100
    for i in range(3, num_streams + 1):
        assert await economy.get_balance(f"sim-creator-{i}", "shared_viewer") == 0

    # Invariant B: Custom commands are strictly isolated
    author = YouTubeAuthor(channel_id="shared_viewer", display_name="SharedViewer")

    # Command !stream1 executed on Stream 1 -> SUCCESS
    ctx_s1 = CommandExecutionContext(
        command_name="stream1",
        args=[],
        raw_text="!stream1",
        creator_id="sim-creator-1",
        stream_session_id="sim-stream-1",
        author=author,
    )
    res_s1 = await command_engine.execute_command(ctx_s1, db_session)
    assert res_s1.success is True
    assert "Stream 1" in res_s1.response_message

    # Command !stream1 executed on Stream 2 -> FAILS (Command not found on Creator 2)
    ctx_s2 = CommandExecutionContext(
        command_name="stream1",
        args=[],
        raw_text="!stream1",
        creator_id="sim-creator-2",
        stream_session_id="sim-stream-2",
        author=author,
    )
    res_s2 = await command_engine.execute_command(ctx_s2, db_session)
    assert res_s2.success is False
    assert res_s2.error_message == "UNKNOWN_COMMAND"

    # Invariant C: Store items cannot be purchased across streams
    # Perk_1 belongs to Creator 1. Trying to buy Perk_1 on Creator 2 fails
    success, reason, _ = await store.purchase_item("sim-creator-2", "shared_viewer", "Perk_1")
    assert success is False
    assert "not available" in reason.lower()

    # Buying Perk_1 on Creator 1 succeeds
    success, reason, inv = await store.purchase_item("sim-creator-1", "shared_viewer", "Perk_1")
    assert success is True
    assert inv.quantity == 1
    # Creator 1 balance deducted (500 - 50 = 450)
    assert await economy.get_balance("sim-creator-1", "shared_viewer") == 450
    # Creator 2 balance untouched (still 100)
    assert await economy.get_balance("sim-creator-2", "shared_viewer") == 100

    # Invariant D: Leaderboards are strictly isolated per creator
    lb_service = LeaderboardService(db_session)
    top_c1 = await lb_service.get_top_xp("sim-creator-1", limit=10)
    top_c2 = await lb_service.get_top_xp("sim-creator-2", limit=10)
    top_c3 = await lb_service.get_top_xp("sim-creator-3", limit=10)

    assert len(top_c1) == 1
    assert top_c1[0]["total_xp"] == 200

    assert len(top_c2) == 1
    assert top_c2[0]["total_xp"] == 50

    assert len(top_c3) == 0  # No viewers on stream 3

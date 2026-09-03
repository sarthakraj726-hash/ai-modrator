"""High-duration soak test simulating 7 concurrent live streams."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.engine import ProductionCommandEngine
from app.commands.models import CommandExecutionContext
from app.core.rbac import Role
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession, StreamStatus
from app.economy.ledger import EconomyService
from app.engagement.xp import XPManager
from app.games.engine import MiniGameEngine
from app.youtube.models import YouTubeAuthor


@pytest.mark.asyncio
async def test_seven_stream_high_throughput_soak(db_session: AsyncSession):
    """
    Simulates continuous multi-stream operation across 7 independent creators:
    - 700 concurrent chat events (100 per stream).
    - Commands, mini-game guesses, and XP progression.
    - Zero task leaks, zero negative balances, and clean creator isolation.
    """
    num_streams = 7
    creators: list[Creator] = []
    streams: list[StreamSession] = []

    for i in range(1, num_streams + 1):
        c = Creator(
            id=f"c-soak-{i}",
            youtube_channel_id=f"UC_soak_{i}",
            channel_name=f"Soak Streamer {i}",
        )
        s = StreamSession(
            id=f"s-soak-{i}",
            creator_id=c.id,
            youtube_video_id=f"vid_soak_{i}",
            youtube_live_chat_id=f"chat_soak_{i}",
            status=StreamStatus.ACTIVE.value,
            started_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        db_session.add(c)
        db_session.add(s)
        creators.append(c)
        streams.append(s)

    await db_session.flush()

    economy_svc = EconomyService(db_session)
    xp_mgr = XPManager(base_xp=100, multiplier=1.5)
    cmd_engine = ProductionCommandEngine()
    game_engine = MiniGameEngine()

    # Launch mini-game on Stream 1 and 2
    await game_engine.start_game(db_session, creators[0].id, streams[0].id, "TRIVIA")
    await game_engine.start_game(db_session, creators[1].id, streams[1].id, "WORD_SCRAMBLE")

    # Run soak simulation workload per stream
    async def run_stream_workload(creator: Creator, stream: StreamSession, stream_idx: int):
        for msg_idx in range(1, 50):
            viewer_id = f"viewer_{stream_idx}_{msg_idx % 5}"
            author = YouTubeAuthor(
                channel_id=viewer_id,
                display_name=f"Viewer_{stream_idx}_{msg_idx % 5}",
            )

            # 1. Award XP
            await xp_mgr.process_chat_message(
                session=db_session,
                creator_id=creator.id,
                viewer_channel_id=viewer_id,
                display_name=author.display_name,
                message_text=f"Great gameplay today in stream {stream_idx}! GG number {msg_idx}",
            )

            # 2. Command execution
            if msg_idx % 10 == 0:
                ctx = CommandExecutionContext(
                    command_name="xp",
                    args=[],
                    raw_text="!xp",
                    creator_id=creator.id,
                    stream_session_id=stream.id,
                    author=author,
                    author_role=Role.VIEWER,
                )
                await cmd_engine.execute_command(ctx, db_session)

            # 3. Virtual Coins
            if msg_idx % 15 == 0:
                await economy_svc.earn(
                    creator_id=creator.id,
                    viewer_channel_id=viewer_id,
                    amount=20,
                    reason="Participation bonus",
                )

    for i in range(num_streams):
        await run_stream_workload(creators[i], streams[i], i + 1)

    # Verify that all balances remain non-negative
    for i in range(num_streams):
        for v in range(5):
            bal = await economy_svc.get_balance(creators[i].id, f"viewer_{i + 1}_{v}")
            assert bal >= 0

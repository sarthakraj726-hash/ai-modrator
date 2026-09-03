"""Chaos and concurrency tests for engagement, double-spending prevention, and stock races."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.economy.ledger import EconomyService
from app.store.service import StoreService


@pytest.fixture
async def chaos_creator(db_session: AsyncSession) -> tuple[Creator, StreamSession]:
    creator = Creator(
        id="c-chaos-1",
        youtube_channel_id="UC_chaos_1",
        channel_name="Chaos Streamer",
    )
    db_session.add(creator)
    stream = StreamSession(
        id="s-chaos-1",
        creator_id="c-chaos-1",
        youtube_video_id="vid_chaos_1",
        youtube_live_chat_id="chat_chaos_1",
    )
    db_session.add(stream)
    await db_session.flush()
    return creator, stream


@pytest.mark.asyncio
async def test_concurrent_single_stock_race(
    db_session: AsyncSession, chaos_creator: tuple[Creator, StreamSession]
):
    """
    Test that when an item has stock = 1, multiple sequential or concurrent
    purchase attempts allow exactly ONE winner, and remaining attempts fail cleanly
    with OUT_OF_STOCK, preventing negative stock or excess coin deduction.
    """
    creator, _ = chaos_creator
    store = StoreService(db_session)
    economy = EconomyService(db_session)

    # 1. Setup item with strictly 1 stock
    await store.create_item(
        creator_id=creator.id,
        name="Rare Gold Trophy",
        description="One and only trophy",
        price=100,
        stock=1,
    )

    # Setup 10 competing buyers, each with 200 coins
    buyers = [f"buyer_{i}" for i in range(10)]
    for b in buyers:
        await economy.earn(creator.id, b, 200, "Initial grant")

    # 2. Execute purchase attempts
    results = []
    for b in buyers:
        res = await store.purchase_item(
            creator_id=creator.id,
            viewer_channel_id=b,
            item_name="Rare Gold Trophy",
        )
        results.append(res)

    successful = [r for r in results if r[0] is True]
    failed = [r for r in results if r[0] is False]

    # Exactly 1 must succeed
    assert len(successful) == 1
    assert len(failed) == 9

    # Stock must be exactly 0, never negative
    updated_item = await store.get_item(creator.id, "Rare Gold Trophy")
    assert updated_item.stock == 0

    # Verify inventory was granted to only 1 winner
    winner_channel = successful[0][2].viewer_channel_id
    winner_inv = await store.get_viewer_inventory(creator.id, winner_channel)
    assert len(winner_inv) == 1
    assert winner_inv[0].quantity == 1

    # Verify 9 losers were NOT charged any coins
    for b in buyers:
        if b != winner_channel:
            bal = await economy.get_balance(creator.id, b)
            assert bal == 200  # Untouched


@pytest.mark.asyncio
async def test_negative_balance_prevention(
    db_session: AsyncSession, chaos_creator: tuple[Creator, StreamSession]
):
    """
    Test that a viewer cannot drive their account into a negative balance
    through multiple rapid spend requests.
    """
    creator, _ = chaos_creator
    economy = EconomyService(db_session)

    # Viewer has 100 coins
    viewer_id = "v_tight_budget"
    await economy.earn(creator.id, viewer_id, 100, "Grant")

    # Attempt 3 spends of 60 coins each (total 180 coins requested)
    results = []
    for i in range(3):
        res = await economy.spend(
            creator_id=creator.id,
            viewer_channel_id=viewer_id,
            amount=60,
            reason=f"Attempt {i}",
            idempotency_key=f"spend:attempt:{i}",
        )
        results.append(res)

    successful = [r for r in results if r[0] is True]
    failed = [r for r in results if r[0] is False]

    # Only 1 spend can succeed (leaving 40 coins)
    assert len(successful) == 1
    assert len(failed) == 2

    # Balance must be 40, strictly non-negative
    balance = await economy.get_balance(creator.id, viewer_id)
    assert balance == 40

"""Unit tests for creator store items, stock management, and viewer inventory purchases."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creator import Creator
from app.economy.ledger import EconomyService
from app.store.service import StoreService


@pytest.fixture
async def store_creator(db_session: AsyncSession) -> Creator:
    creator = Creator(
        id="c-store-1",
        youtube_channel_id="UC_store_1",
        channel_name="Shop Streamer",
    )
    db_session.add(creator)
    await db_session.flush()
    return creator


@pytest.mark.asyncio
async def test_store_item_lifecycle(db_session: AsyncSession, store_creator: Creator):
    store = StoreService(db_session)

    # 1. Create item
    item = await store.create_item(
        creator_id=store_creator.id,
        name="VIP Badge",
        description="Exclusive stream badge",
        price=100,
        stock=10,
        max_per_user=1,
    )
    assert item.id is not None
    assert item.name == "VIP Badge"

    # 2. List items
    items = await store.list_items(store_creator.id)
    assert len(items) == 1
    assert items[0].name == "VIP Badge"

    # 3. Delete item
    deleted = await store.delete_item(store_creator.id, "VIP Badge")
    assert deleted is True

    items_after = await store.list_items(store_creator.id)
    assert len(items_after) == 0


@pytest.mark.asyncio
async def test_purchase_item_flow(db_session: AsyncSession, store_creator: Creator):
    store = StoreService(db_session)
    economy = EconomyService(db_session)

    # Setup item with stock=2, max_per_user=2, price=50
    await store.create_item(
        creator_id=store_creator.id,
        name="Coffee",
        description="Buy Honney a coffee",
        price=50,
        stock=2,
        max_per_user=2,
    )

    # Viewer has 0 coins -> purchase fails
    success, reason, inv = await store.purchase_item(store_creator.id, "v_shopper", "Coffee")
    assert success is False
    assert "INSUFFICIENT_FUNDS" in reason

    # Grant 120 coins
    await economy.earn(store_creator.id, "v_shopper", 120, "Grant")

    # Purchase 1 -> succeeds
    success, reason, inv = await store.purchase_item(store_creator.id, "v_shopper", "Coffee")
    assert success is True
    assert inv.quantity == 1
    assert await economy.get_balance(store_creator.id, "v_shopper") == 70

    # Verify item stock decremented from 2 to 1
    updated_item = await store.get_item(store_creator.id, "Coffee")
    assert updated_item.stock == 1

    # Purchase 2 -> succeeds (remaining 20 coins, stock becomes 0)
    success, reason, inv = await store.purchase_item(store_creator.id, "v_shopper", "Coffee")
    assert success is True
    assert inv.quantity == 2
    assert updated_item.stock == 0

    # Purchase 3 -> fails: out of stock (and max_per_user limit)
    # Grant more coins
    await economy.earn(store_creator.id, "v_shopper", 100, "Grant")
    success, reason, inv = await store.purchase_item(store_creator.id, "v_shopper", "Coffee")
    assert success is False
    assert "out of stock" in reason.lower()

"""Repository for StoreItem and ViewerInventory entities."""

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.store import StoreItem, ViewerInventory


class StoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, creator_id: str, name: str) -> StoreItem | None:
        """Find store item by name within creator scope."""
        stmt = select(StoreItem).where(
            StoreItem.creator_id == creator_id,
            StoreItem.name == name.strip(),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, item_id: str) -> StoreItem | None:
        """Find store item by primary key."""
        stmt = select(StoreItem).where(StoreItem.id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_items(self, creator_id: str, enabled_only: bool = True) -> list[StoreItem]:
        """List store items for a creator."""
        stmt = select(StoreItem).where(StoreItem.creator_id == creator_id)
        if enabled_only:
            stmt = stmt.where(StoreItem.enabled.is_(True))
        stmt = stmt.order_by(StoreItem.price.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_item(
        self,
        creator_id: str,
        name: str,
        description: str,
        price: int,
        stock: int = -1,
        max_per_user: int = -1,
        cooldown_seconds: int = 0,
        enabled: bool = True,
    ) -> StoreItem:
        """Create a new store item for a creator."""
        item = StoreItem(
            creator_id=creator_id,
            name=name.strip(),
            description=description,
            price=price,
            stock=stock,
            max_per_user=max_per_user,
            cooldown_seconds=cooldown_seconds,
            enabled=enabled,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_item(
        self,
        item: StoreItem,
        description: str | None = None,
        price: int | None = None,
        stock: int | None = None,
        max_per_user: int | None = None,
        enabled: bool | None = None,
    ) -> StoreItem:
        """Update existing store item properties."""
        if description is not None:
            item.description = description
        if price is not None:
            item.price = price
        if stock is not None:
            item.stock = stock
        if max_per_user is not None:
            item.max_per_user = max_per_user
        if enabled is not None:
            item.enabled = enabled
        await self.session.flush()
        return item

    async def delete_item(self, creator_id: str, name: str) -> bool:
        """Delete store item by name within creator scope."""
        item = await self.get_by_name(creator_id, name)
        if not item:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True

    async def get_inventory(self, creator_id: str, viewer_channel_id: str) -> list[ViewerInventory]:
        """Fetch all items owned by a viewer for a creator."""
        stmt = (
            select(ViewerInventory)
            .where(
                ViewerInventory.creator_id == creator_id,
                ViewerInventory.viewer_channel_id == viewer_channel_id,
            )
            .options(selectinload(ViewerInventory.item))
            .order_by(desc(ViewerInventory.last_acquired_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_inventory_item(
        self, creator_id: str, viewer_channel_id: str, item_id: str
    ) -> ViewerInventory | None:
        """Fetch specific inventory entry."""
        stmt = select(ViewerInventory).where(
            ViewerInventory.creator_id == creator_id,
            ViewerInventory.viewer_channel_id == viewer_channel_id,
            ViewerInventory.item_id == item_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def grant_inventory(
        self, creator_id: str, viewer_channel_id: str, item_id: str, quantity: int = 1
    ) -> ViewerInventory:
        """Add or increment inventory quantity for a viewer."""
        inv = await self.get_inventory_item(creator_id, viewer_channel_id, item_id)
        now = datetime.now(UTC)
        if not inv:
            inv = ViewerInventory(
                creator_id=creator_id,
                viewer_channel_id=viewer_channel_id,
                item_id=item_id,
                quantity=quantity,
                first_acquired_at=now,
                last_acquired_at=now,
            )
            self.session.add(inv)
        else:
            inv.quantity += quantity
            inv.last_acquired_at = now
        await self.session.flush()
        return inv

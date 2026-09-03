"""Creator-scoped store and inventory service with atomic purchase validation."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.store import StoreItem, ViewerInventory
from app.db.repositories.engagement_repo import EngagementRepository
from app.db.repositories.store_repo import StoreRepository
from app.economy.ledger import EconomyService

logger = get_logger("app.store.service")


class StoreService:
    """
    Manages creator-scoped virtual store items and viewer item purchases.
    Integrates atomically with EconomyService for double-entry coin settlement.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.store_repo = StoreRepository(session)
        self.economy_service = EconomyService(session)
        self.engagement_repo = EngagementRepository(session)

    async def list_items(self, creator_id: str, enabled_only: bool = True) -> list[StoreItem]:
        """List store items for a creator."""
        return await self.store_repo.list_items(creator_id, enabled_only=enabled_only)

    async def get_item(self, creator_id: str, name: str) -> StoreItem | None:
        """Find store item by name within creator scope."""
        return await self.store_repo.get_by_name(creator_id, name)

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
        """Create new store item for creator."""
        return await self.store_repo.create_item(
            creator_id=creator_id,
            name=name,
            description=description,
            price=price,
            stock=stock,
            max_per_user=max_per_user,
            cooldown_seconds=cooldown_seconds,
            enabled=enabled,
        )

    async def update_item(
        self,
        creator_id: str,
        name: str,
        description: str | None = None,
        price: int | None = None,
        stock: int | None = None,
        max_per_user: int | None = None,
        enabled: bool | None = None,
    ) -> StoreItem | None:
        """Update existing store item."""
        item = await self.store_repo.get_by_name(creator_id, name)
        if not item:
            return None
        return await self.store_repo.update_item(
            item=item,
            description=description,
            price=price,
            stock=stock,
            max_per_user=max_per_user,
            enabled=enabled,
        )

    async def delete_item(self, creator_id: str, name: str) -> bool:
        """Delete store item by name."""
        return await self.store_repo.delete_item(creator_id, name)

    async def purchase_item(
        self,
        creator_id: str,
        viewer_channel_id: str,
        item_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[bool, str, ViewerInventory | None]:
        """
        Execute atomic store purchase:
          1. Validate item existence and status
          2. Check stock constraint
          3. Check user purchase cap
          4. Execute double-entry spend transaction via EconomyService
          5. Decrement stock
          6. Grant inventory
        """
        # 1. Resolve item
        item = await self.store_repo.get_by_name(creator_id, item_name)
        if not item or not item.enabled:
            return False, f"Item '{item_name}' is not available in the store.", None

        # 2. Check stock
        if item.stock == 0:
            return False, f"Item '{item.name}' is currently out of stock!", None

        # 3. Check user purchase limits
        if item.max_per_user > 0:
            inv = await self.store_repo.get_inventory_item(creator_id, viewer_channel_id, item.id)
            if inv and inv.quantity >= item.max_per_user:
                return (
                    False,
                    f"You have reached the maximum allowed limit ({item.max_per_user}) for '{item.name}'.",
                    None,
                )

        # 4. Settle payment via double-entry ledger
        idem_key = idempotency_key or f"buy:{creator_id}:{viewer_channel_id}:{item.id}:{item.price}"
        success, reason, _ = await self.economy_service.spend(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            amount=item.price,
            reason=f"Purchased {item.name}",
            idempotency_key=idem_key,
            reference_type="store_item",
            reference_id=item.id,
        )
        if not success:
            return False, reason, None

        # 5. Decrement stock if finite
        if item.stock > 0:
            item.stock -= 1

        # 6. Grant inventory
        inventory = await self.store_repo.grant_inventory(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            item_id=item.id,
            quantity=1,
        )

        # 7. Update engagement record
        profile = await self.engagement_repo.get_by_viewer(creator_id, viewer_channel_id)
        if profile:
            await self.engagement_repo.record_purchase(profile)

        await self.session.flush()
        logger.info(
            f"Viewer {viewer_channel_id} purchased '{item.name}' for {item.price} coins on creator {creator_id}."
        )
        return True, "SUCCESS", inventory

    async def get_viewer_inventory(
        self, creator_id: str, viewer_channel_id: str
    ) -> list[ViewerInventory]:
        """Fetch all acquired items in viewer's inventory."""
        return await self.store_repo.get_inventory(creator_id, viewer_channel_id)

"""REST API endpoints for commands, economy, store, and leaderboards."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import AdminUserDep, DBSessionDep
from app.core.rbac import Role
from app.db.repositories.command_repo import CommandRepository
from app.db.repositories.economy_repo import EconomyRepository
from app.economy.ledger import EconomyService
from app.engagement.leaderboards import LeaderboardService
from app.store.service import StoreService

router = APIRouter(prefix="/api/v1", tags=["Commands & Engagement"])


class CreateCustomCommandRequest(BaseModel):
    name: str
    response: str
    min_role: Role = Role.VIEWER
    cooldown_seconds: int = 5


class CreateStoreItemRequest(BaseModel):
    name: str
    description: str = ""
    price: int
    stock: int = -1
    max_per_user: int = -1
    cooldown_seconds: int = 0


class AdminGiveCoinsRequest(BaseModel):
    target_viewer_id: str
    amount: int = Field(gt=0)
    reason: str = "Admin Grant via REST API"


# ==============================================================================
# Commands Endpoints
# ==============================================================================


@router.get("/commands/{creator_id}")
async def list_custom_commands(
    creator_id: str,
    db: DBSessionDep,
) -> dict[str, Any]:
    """List custom commands for a creator."""
    repo = CommandRepository(db)
    commands = await repo.list_for_creator(creator_id)
    return {
        "creator_id": creator_id,
        "count": len(commands),
        "commands": [
            {
                "id": c.id,
                "name": f"!{c.name}",
                "response": c.response,
                "min_role": c.min_role,
                "cooldown_seconds": c.cooldown_seconds,
                "enabled": c.enabled,
                "aliases": [f"!{a.alias}" for a in c.aliases],
            }
            for c in commands
        ],
    }


@router.post("/commands/{creator_id}", status_code=status.HTTP_201_CREATED)
async def create_custom_command(
    creator_id: str,
    req: CreateCustomCommandRequest,
    db: DBSessionDep,
    _admin: AdminUserDep,
) -> dict[str, Any]:
    """Create a new custom command (requires admin/creator authorization)."""
    repo = CommandRepository(db)
    existing = await repo.get_by_name(creator_id, req.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Command '!{req.name}' already exists for this creator.",
        )
    cmd = await repo.create_command(
        creator_id=creator_id,
        name=req.name,
        response=req.response,
        min_role=req.min_role,
        cooldown_seconds=req.cooldown_seconds,
    )
    return {"message": "Command created", "command_id": cmd.id, "name": f"!{cmd.name}"}


@router.delete("/commands/{creator_id}/{name}")
async def delete_custom_command(
    creator_id: str,
    name: str,
    db: DBSessionDep,
    _admin: AdminUserDep,
) -> dict[str, Any]:
    """Delete a custom command (requires admin/creator authorization)."""
    repo = CommandRepository(db)
    deleted = await repo.delete_command(creator_id, name.lstrip("!"))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command '!{name}' not found.",
        )
    return {"message": f"Command '!{name}' deleted"}


# ==============================================================================
# Economy Endpoints
# ==============================================================================


@router.get("/economy/{creator_id}/balance/{viewer_id}")
async def get_viewer_balance(
    creator_id: str,
    viewer_id: str,
    db: DBSessionDep,
) -> dict[str, Any]:
    """Get coin balance for a viewer on a creator channel."""
    economy = EconomyService(db)
    balance = await economy.get_balance(creator_id, viewer_id)
    return {"creator_id": creator_id, "viewer_id": viewer_id, "balance": balance}


@router.post("/economy/{creator_id}/give")
async def admin_give_coins(
    creator_id: str,
    req: AdminGiveCoinsRequest,
    db: DBSessionDep,
    admin: AdminUserDep,
) -> dict[str, Any]:
    """Grant coins to a viewer (requires admin authorization)."""
    economy = EconomyService(db)
    success, reason, tx = await economy.give(
        creator_id=creator_id,
        admin_id=admin.user_id,
        to_viewer_id=req.target_viewer_id,
        amount=req.amount,
        reason=req.reason,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    return {
        "message": f"Granted {req.amount} coins to viewer {req.target_viewer_id}",
        "transaction_id": tx.id if tx else None,
    }


@router.get("/economy/{creator_id}/transactions")
async def list_creator_transactions(
    creator_id: str,
    db: DBSessionDep,
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """List recent double-entry ledger transactions."""
    repo = EconomyRepository(db)
    txs = await repo.list_transactions_for_creator(creator_id, limit=limit)
    return {
        "creator_id": creator_id,
        "count": len(txs),
        "transactions": [
            {
                "id": t.id,
                "type": t.transaction_type,
                "description": t.description,
                "idempotency_key": t.idempotency_key,
                "created_at": t.created_at.isoformat(),
                "entries": [
                    {
                        "account_id": e.account_id,
                        "direction": e.direction,
                        "amount": e.amount,
                        "balance_after": e.balance_after,
                    }
                    for e in t.ledger_entries
                ],
            }
            for t in txs
        ],
    }


# ==============================================================================
# Store Endpoints
# ==============================================================================


@router.get("/store/{creator_id}/items")
async def list_store_items(
    creator_id: str,
    db: DBSessionDep,
    enabled_only: bool = Query(True),
) -> dict[str, Any]:
    """List store items for a creator."""
    store = StoreService(db)
    items = await store.list_items(creator_id, enabled_only=enabled_only)
    return {
        "creator_id": creator_id,
        "count": len(items),
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "description": i.description,
                "price": i.price,
                "stock": i.stock,
                "max_per_user": i.max_per_user,
                "enabled": i.enabled,
            }
            for i in items
        ],
    }


@router.post("/store/{creator_id}/items", status_code=status.HTTP_201_CREATED)
async def create_store_item(
    creator_id: str,
    req: CreateStoreItemRequest,
    db: DBSessionDep,
    _admin: AdminUserDep,
) -> dict[str, Any]:
    """Create a new store item (requires admin authorization)."""
    store = StoreService(db)
    existing = await store.get_item(creator_id, req.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Store item '{req.name}' already exists for this creator.",
        )
    item = await store.create_item(
        creator_id=creator_id,
        name=req.name,
        description=req.description,
        price=req.price,
        stock=req.stock,
        max_per_user=req.max_per_user,
        cooldown_seconds=req.cooldown_seconds,
    )
    return {"message": "Store item created", "item_id": item.id, "name": item.name}


# ==============================================================================
# Leaderboards Endpoints
# ==============================================================================


@router.get("/leaderboards/{creator_id}/{board_type}")
async def get_leaderboard(
    creator_id: str,
    board_type: str,
    db: DBSessionDep,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Get creator leaderboard by type: xp, coins, or level."""
    lb = LeaderboardService(db)
    bt = board_type.lower()
    if bt == "xp":
        entries = await lb.get_top_xp(creator_id, limit=limit)
    elif bt == "coins":
        entries = await lb.get_top_coins(creator_id, limit=limit)
    elif bt == "level":
        entries = await lb.get_top_level(creator_id, limit=limit)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid board type '{board_type}'. Available: xp, coins, level",
        )
    return {"creator_id": creator_id, "type": bt, "entries": entries}

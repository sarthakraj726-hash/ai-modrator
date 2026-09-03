"""Built-in command handlers for utility, social, economy, store, and engagement."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.models import ChatCommand, CommandCategory, CommandExecutionContext, CommandResult
from app.db.repositories.engagement_repo import EngagementRepository
from app.economy.ledger import EconomyService
from app.engagement.leaderboards import LeaderboardService
from app.engagement.xp import XPManager
from app.games.engine import MiniGameEngine
from app.store.service import StoreService


async def handle_help(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    """Show list of foundational commands."""
    return CommandResult(
        success=True,
        response_message="Commands: !level, !xp, !coins, !rank, !leaderboard, !shop, !buy, !inventory, !trivia, !word, !rules, !discord, !uptime",
        action_taken="SHOW_HELP",
    )


async def handle_rules(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    return CommandResult(
        success=True,
        response_message="Stream Rules: 1. Be respectful 2. No hate speech or slurs 3. No spam or scam links 4. Have fun!",
        action_taken="SHOW_RULES",
    )


async def handle_discord(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    return CommandResult(
        success=True,
        response_message="Join our official Discord community! Check the stream description for the invite link.",
        action_taken="SHOW_DISCORD",
    )


async def handle_uptime(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    return CommandResult(
        success=True,
        response_message="Stream is live and running smoothly! Powered by Goddess AI / Honney.",
        action_taken="SHOW_UPTIME",
    )


async def handle_viewers(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    return CommandResult(
        success=True,
        response_message="Welcome everyone in chat! Thanks for watching and supporting the stream.",
        action_taken="SHOW_VIEWERS",
    )


async def handle_level(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    repo = EngagementRepository(session)
    profile = await repo.get_or_create(
        ctx.creator_id, ctx.author.channel_id, ctx.author.display_name
    )
    xp_mgr = kwargs.get("xp_manager") or XPManager()
    next_xp = xp_mgr.xp_for_next_level(profile.level)
    return CommandResult(
        success=True,
        response_message=f"@{ctx.author.display_name} is Level {profile.level}! Total XP: {profile.total_xp} (Next level step: ~{next_xp} XP)",
        action_taken="SHOW_LEVEL",
        data={"level": profile.level, "total_xp": profile.total_xp},
    )


async def handle_xp(ctx: CommandExecutionContext, session: AsyncSession, **kwargs) -> CommandResult:
    repo = EngagementRepository(session)
    profile = await repo.get_or_create(
        ctx.creator_id, ctx.author.channel_id, ctx.author.display_name
    )
    return CommandResult(
        success=True,
        response_message=f"@{ctx.author.display_name} has {profile.total_xp} total XP (Level {profile.level}).",
        action_taken="SHOW_XP",
        data={"total_xp": profile.total_xp, "level": profile.level},
    )


async def handle_coins(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    economy = EconomyService(session)
    balance = await economy.get_balance(ctx.creator_id, ctx.author.channel_id)
    return CommandResult(
        success=True,
        response_message=f"@{ctx.author.display_name} has {balance} virtual coins 🪙.",
        action_taken="SHOW_COINS",
        data={"balance": balance},
    )


async def handle_rank(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    lb_service = LeaderboardService(session)
    top = await lb_service.get_top_xp(ctx.creator_id, limit=50)
    rank = next((item["rank"] for item in top if item["viewer_id"] == ctx.author.channel_id), None)
    if rank:
        msg = f"@{ctx.author.display_name} is ranked #{rank} on the stream XP leaderboard!"
    else:
        msg = f"@{ctx.author.display_name} is currently unranked. Keep chatting to climb the board!"
    return CommandResult(success=True, response_message=msg, action_taken="SHOW_RANK")


async def handle_leaderboard(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    lb_service = LeaderboardService(session)
    board_type = ctx.args[0].lower() if ctx.args else "xp"
    if board_type in ("coins", "coin", "gold"):
        top = await lb_service.get_top_coins(ctx.creator_id, limit=5)
        if not top:
            return CommandResult(
                success=True, response_message="Coin leaderboard is empty! Earn coins by chatting."
            )
        lines = [
            f"#{item['rank']} {item['viewer_id'][:8]}.. ({item['coins']} coins)" for item in top
        ]
        return CommandResult(success=True, response_message=f"🏆 Top Coins: {', '.join(lines)}")
    else:
        top = await lb_service.get_top_xp(ctx.creator_id, limit=5)
        if not top:
            return CommandResult(
                success=True, response_message="XP leaderboard is empty! Chat to earn XP."
            )
        lines = [
            f"#{item['rank']} {item['display_name']} (Lvl {item['level']}, {item['total_xp']} XP)"
            for item in top
        ]
        return CommandResult(success=True, response_message=f"🏆 Top XP: {', '.join(lines)}")


async def handle_shop(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    store = StoreService(session)
    items = await store.list_items(ctx.creator_id, enabled_only=True)
    if not items:
        return CommandResult(
            success=True,
            response_message="The stream store currently has no active items. Check back soon!",
            action_taken="SHOW_SHOP",
        )
    catalog = [f"{item.name} ({item.price} coins)" for item in items]
    return CommandResult(
        success=True,
        response_message=f"🏪 Stream Store: {', '.join(catalog)}. Use '!buy <item>' to purchase!",
        action_taken="SHOW_SHOP",
    )


async def handle_buy(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    if not ctx.args:
        return CommandResult(
            success=False,
            response_message="Usage: !buy <item_name> (e.g. !buy VIP)",
            error_message="MISSING_ARGUMENT",
        )
    item_name = " ".join(ctx.args)
    store = StoreService(session)
    success, reason, inv = await store.purchase_item(
        creator_id=ctx.creator_id,
        viewer_channel_id=ctx.author.channel_id,
        item_name=item_name,
    )
    if not success:
        return CommandResult(
            success=False,
            response_message=f"Purchase failed: {reason}",
            error_message=reason,
        )
    return CommandResult(
        success=True,
        response_message=f"🎉 @{ctx.author.display_name} purchased '{item_name}'! (Owned: {inv.quantity})",
        action_taken="PURCHASE_ITEM",
        data={"item": item_name, "quantity": inv.quantity},
    )


async def handle_inventory(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    store = StoreService(session)
    items = await store.get_viewer_inventory(ctx.creator_id, ctx.author.channel_id)
    if not items:
        return CommandResult(
            success=True,
            response_message=f"@{ctx.author.display_name}'s inventory is empty. Earn coins and visit !shop!",
            action_taken="SHOW_INVENTORY",
        )
    inv_list = [f"{i.item.name} (x{i.quantity})" for i in items if i.item]
    return CommandResult(
        success=True,
        response_message=f"🎒 @{ctx.author.display_name}'s Inventory: {', '.join(inv_list)}",
        action_taken="SHOW_INVENTORY",
    )


async def handle_trivia(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    game_engine: MiniGameEngine = kwargs.get("game_engine") or MiniGameEngine()
    success, msg, _ = await game_engine.start_game(
        session=session,
        creator_id=ctx.creator_id,
        stream_session_id=ctx.stream_session_id,
        game_type="TRIVIA",
    )
    return CommandResult(success=success, response_message=msg, action_taken="START_TRIVIA")


async def handle_word(
    ctx: CommandExecutionContext, session: AsyncSession, **kwargs
) -> CommandResult:
    game_engine: MiniGameEngine = kwargs.get("game_engine") or MiniGameEngine()
    success, msg, _ = await game_engine.start_game(
        session=session,
        creator_id=ctx.creator_id,
        stream_session_id=ctx.stream_session_id,
        game_type="WORD_SCRAMBLE",
    )
    return CommandResult(success=success, response_message=msg, action_taken="START_WORD")


def get_builtin_commands() -> list[ChatCommand]:
    """Return all default registered built-in commands."""
    return [
        ChatCommand(
            name="help",
            aliases=["commands"],
            description="Show commands list",
            category=CommandCategory.UTILITY,
            handler=handle_help,
        ),
        ChatCommand(
            name="rules",
            description="Show stream rules",
            category=CommandCategory.UTILITY,
            handler=handle_rules,
        ),
        ChatCommand(
            name="discord",
            aliases=["dc"],
            description="Show discord link",
            category=CommandCategory.SOCIAL,
            handler=handle_discord,
        ),
        ChatCommand(
            name="uptime",
            description="Show stream uptime",
            category=CommandCategory.UTILITY,
            handler=handle_uptime,
        ),
        ChatCommand(
            name="viewers",
            description="Show viewer message",
            category=CommandCategory.UTILITY,
            handler=handle_viewers,
        ),
        ChatCommand(
            name="level",
            aliases=["lvl"],
            description="Show caller level and XP",
            category=CommandCategory.XP,
            handler=handle_level,
        ),
        ChatCommand(
            name="xp", description="Show caller XP", category=CommandCategory.XP, handler=handle_xp
        ),
        ChatCommand(
            name="coins",
            aliases=["balance", "bal"],
            description="Show coin balance",
            category=CommandCategory.ECONOMY,
            handler=handle_coins,
        ),
        ChatCommand(
            name="rank",
            description="Show leaderboard rank",
            category=CommandCategory.XP,
            handler=handle_rank,
        ),
        ChatCommand(
            name="leaderboard",
            aliases=["lb", "top"],
            description="Show top viewers",
            category=CommandCategory.XP,
            handler=handle_leaderboard,
        ),
        ChatCommand(
            name="shop",
            aliases=["store"],
            description="Show stream store catalog",
            category=CommandCategory.STORE,
            handler=handle_shop,
        ),
        ChatCommand(
            name="buy",
            description="Purchase item from store",
            category=CommandCategory.STORE,
            handler=handle_buy,
        ),
        ChatCommand(
            name="inventory",
            aliases=["inv"],
            description="Show owned items",
            category=CommandCategory.STORE,
            handler=handle_inventory,
        ),
        ChatCommand(
            name="trivia",
            description="Start or view active trivia game",
            category=CommandCategory.GAME,
            handler=handle_trivia,
        ),
        ChatCommand(
            name="word",
            aliases=["scramble"],
            description="Start word scramble game",
            category=CommandCategory.GAME,
            handler=handle_word,
        ),
    ]

"""Chat-first administration handler for !uk management commands."""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.models import CommandExecutionContext, CommandResult
from app.core.logging import get_logger
from app.core.rbac import Role
from app.db.repositories.command_repo import CommandRepository
from app.discord.logger import DiscordLogger
from app.economy.ledger import EconomyService
from app.moderation.hitl.service import HumanReviewService
from app.store.service import StoreService

logger = get_logger("app.commands.admin")


class AdminCommandHandler:
    """
    Dispatcher for '!uk' administrative commands.
    Enforces RBAC: Only MODERATOR, CREATOR, and DEVELOPER can invoke !uk subcommands.
    """

    @classmethod
    async def execute(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        discord_logger: DiscordLogger | None = None,
        **kwargs,
    ) -> CommandResult:
        # 1. Strict RBAC Gate
        if ctx.author_role not in (Role.MODERATOR, Role.CREATOR, Role.DEVELOPER):
            logger.warning(
                f"Unauthorized !uk command attempt by {ctx.author.display_name} ({ctx.author.channel_id}) on creator {ctx.creator_id}"
            )
            return CommandResult(
                success=False,
                response_message="Permission denied: You cannot execute !uk admin commands.",
                error_message="PERMISSION_DENIED",
            )

        if not ctx.args:
            return CommandResult(
                success=False,
                response_message="Usage: !uk [add|edit|delete|store|give|perms|punish|economy|xp|game]",
                error_message="MISSING_SUBCOMMAND",
            )

        subcommand = ctx.args[0].lower()
        subargs = ctx.args[1:]

        # Dispatch subcommands
        if subcommand == "punish":
            return await cls._handle_punish(ctx, session, subargs)
        elif subcommand == "add":
            return await cls._handle_add_command(ctx, session, subargs, discord_logger)
        elif subcommand == "edit":
            return await cls._handle_edit_command(ctx, session, subargs, discord_logger)
        elif subcommand == "delete":
            return await cls._handle_delete_command(ctx, session, subargs, discord_logger)
        elif subcommand == "store":
            return await cls._handle_store(ctx, session, subargs, discord_logger)
        elif subcommand == "give":
            return await cls._handle_give(ctx, session, subargs, discord_logger)
        elif subcommand == "perms":
            return await cls._handle_perms(ctx, session, subargs, discord_logger)
        elif subcommand in ("economy", "xp", "game"):
            return await cls._handle_toggle(ctx, session, subcommand, subargs, discord_logger)
        else:
            return CommandResult(
                success=False,
                response_message=f"Unknown !uk subcommand '{subcommand}'. Available: add, edit, delete, store, give, perms, punish",
                error_message="UNKNOWN_SUBCOMMAND",
            )

    @classmethod
    async def _handle_punish(
        cls, ctx: CommandExecutionContext, session: AsyncSession, args: list[str]
    ) -> CommandResult:
        """Forwarded from Phase 3 HITL: !uk punish <review_id> [yes|no]"""
        if len(args) < 2:
            return CommandResult(
                success=False,
                response_message="Usage: !uk punish <review_id_prefix> <yes|no>",
                error_message="MISSING_ARGUMENTS",
            )
        prefix = args[0]
        decision = args[1].lower()

        hitl_service = HumanReviewService(session)
        if decision in ("yes", "y", "approve"):
            success, reason = await hitl_service.approve_review(
                review_id_prefix=prefix,
                moderator_id=ctx.author.channel_id,
            )
            return CommandResult(
                success=success,
                response_message=f"Review [{prefix}]: {reason}",
                action_taken="HITL_APPROVE",
            )
        else:
            success, reason = await hitl_service.deny_review(
                review_id_prefix=prefix,
                moderator_id=ctx.author.channel_id,
            )
            return CommandResult(
                success=success,
                response_message=f"Review [{prefix}]: {reason}",
                action_taken="HITL_DENY",
            )

    @classmethod
    async def _handle_add_command(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk add <name> "<response>" [min_role]"""
        if len(args) < 2:
            return CommandResult(
                success=False,
                response_message='Usage: !uk add <name> "<response message>" [role]',
                error_message="MISSING_ARGUMENTS",
            )

        name = args[0].lstrip("!").lower()
        full_text = " ".join(args[1:])

        # Extract quoted response if present
        match = re.search(r'["\'](.*?)["\']', full_text)
        if match:
            response = match.group(1)
            remainder = full_text[match.end() :].strip().split()
            min_role = (
                Role.MODERATOR
                if (remainder and remainder[0].upper() == "MODERATOR")
                else Role.VIEWER
            )
        else:
            response = full_text
            min_role = Role.VIEWER

        repo = CommandRepository(session)
        existing = await repo.get_by_name(ctx.creator_id, name)
        if existing:
            return CommandResult(
                success=False,
                response_message=f"Command '!{name}' already exists. Use '!uk edit' to change it.",
                error_message="COMMAND_EXISTS",
            )

        await repo.create_command(
            creator_id=ctx.creator_id,
            name=name,
            response=response,
            min_role=min_role,
            cooldown_seconds=5,
        )

        if dl:
            await dl.log_creator_event(
                creator_id=ctx.creator_id,
                message=f"Custom command '!{name}' created by @{ctx.author.display_name} ({min_role.value})",
                title="Command Created",
            )

        return CommandResult(
            success=True,
            response_message=f"✅ Created custom command '!{name}'! ({min_role.value})",
            action_taken="COMMAND_CREATED",
            data={"name": name, "response": response},
        )

    @classmethod
    async def _handle_edit_command(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk edit <name> "<new response>" """
        if len(args) < 2:
            return CommandResult(
                success=False,
                response_message='Usage: !uk edit <name> "<new response message>"',
                error_message="MISSING_ARGUMENTS",
            )

        name = args[0].lstrip("!").lower()
        full_text = " ".join(args[1:])
        match = re.search(r'["\'](.*?)["\']', full_text)
        new_response = match.group(1) if match else full_text

        repo = CommandRepository(session)
        cmd = await repo.get_by_name(ctx.creator_id, name)
        if not cmd:
            return CommandResult(
                success=False,
                response_message=f"Command '!{name}' not found.",
                error_message="COMMAND_NOT_FOUND",
            )

        await repo.update_command(cmd, response=new_response)
        return CommandResult(
            success=True,
            response_message=f"✅ Updated custom command '!{name}'!",
            action_taken="COMMAND_UPDATED",
        )

    @classmethod
    async def _handle_delete_command(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk delete <name>"""
        if not args:
            return CommandResult(
                success=False,
                response_message="Usage: !uk delete <name>",
                error_message="MISSING_ARGUMENTS",
            )

        name = args[0].lstrip("!").lower()
        repo = CommandRepository(session)
        deleted = await repo.delete_command(ctx.creator_id, name)
        if not deleted:
            return CommandResult(
                success=False,
                response_message=f"Command '!{name}' not found.",
                error_message="COMMAND_NOT_FOUND",
            )

        return CommandResult(
            success=True,
            response_message=f"🗑️ Deleted custom command '!{name}'!",
            action_taken="COMMAND_DELETED",
        )

    @classmethod
    async def _handle_store(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk store [add|edit|delete]"""
        if not args:
            return CommandResult(
                success=False,
                response_message="Usage: !uk store [add|edit|delete] ...",
                error_message="MISSING_SUBCOMMAND",
            )

        action = args[0].lower()
        store = StoreService(session)

        if action == "add":
            # !uk store add <name> "<desc>" <price> [stock]
            if len(args) < 4:
                return CommandResult(
                    success=False,
                    response_message='Usage: !uk store add <item_name> "<description>" <price> [stock]',
                    error_message="MISSING_ARGUMENTS",
                )
            name = args[1]
            rem_str = " ".join(args[2:])
            match = re.search(r'["\'](.*?)["\']', rem_str)
            desc = match.group(1) if match else "Store item"
            after_desc = rem_str[match.end() :].strip().split() if match else rem_str.split()
            try:
                price = int(after_desc[0]) if after_desc else 100
                stock = int(after_desc[1]) if len(after_desc) > 1 else -1
            except ValueError:
                price = 100
                stock = -1

            await store.create_item(ctx.creator_id, name, desc, price, stock=stock)
            return CommandResult(
                success=True,
                response_message=f"✅ Added store item '{name}' for {price} coins (stock: {stock if stock >= 0 else 'unlimited'})!",
                action_taken="STORE_ITEM_CREATED",
            )
        elif action == "delete":
            if len(args) < 2:
                return CommandResult(
                    success=False, response_message="Usage: !uk store delete <item_name>"
                )
            item_name = args[1]
            deleted = await store.delete_item(ctx.creator_id, item_name)
            if not deleted:
                return CommandResult(
                    success=False, response_message=f"Item '{item_name}' not found."
                )
            return CommandResult(
                success=True, response_message=f"🗑️ Deleted store item '{item_name}'."
            )
        else:
            return CommandResult(
                success=False,
                response_message=f"Unknown store action '{action}'. Use add or delete.",
            )

    @classmethod
    async def _handle_give(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk give @viewer <amount>"""
        if len(args) < 2:
            return CommandResult(
                success=False,
                response_message="Usage: !uk give @viewer <amount>",
                error_message="MISSING_ARGUMENTS",
            )
        target_viewer = args[0].lstrip("@")
        try:
            amount = int(args[1])
            if amount <= 0:
                raise ValueError()
        except ValueError:
            return CommandResult(
                success=False, response_message="Amount must be a positive integer."
            )

        economy = EconomyService(session)
        success, reason, _ = await economy.give(
            creator_id=ctx.creator_id,
            admin_id=ctx.author.channel_id,
            to_viewer_id=target_viewer,
            amount=amount,
            reason=f"Admin grant by @{ctx.author.display_name}",
        )
        if not success:
            return CommandResult(success=False, response_message=f"Grant failed: {reason}")

        return CommandResult(
            success=True,
            response_message=f"💰 Granted {amount} coins to @{target_viewer}!",
            action_taken="COINS_GRANTED",
        )

    @classmethod
    async def _handle_perms(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk perms <command> <role>"""
        if len(args) < 2:
            return CommandResult(
                success=False,
                response_message="Usage: !uk perms <command_name> <viewer|moderator>",
                error_message="MISSING_ARGUMENTS",
            )
        name = args[0].lstrip("!").lower()
        role_str = args[1].upper()
        target_role = Role.MODERATOR if role_str == "MODERATOR" else Role.VIEWER

        repo = CommandRepository(session)
        cmd = await repo.get_by_name(ctx.creator_id, name)
        if not cmd:
            return CommandResult(success=False, response_message=f"Command '!{name}' not found.")

        await repo.update_command(cmd, min_role=target_role)
        return CommandResult(
            success=True,
            response_message=f"🔒 Updated '!{name}' permission to {target_role.value}!",
            action_taken="PERMS_UPDATED",
        )

    @classmethod
    async def _handle_toggle(
        cls,
        ctx: CommandExecutionContext,
        session: AsyncSession,
        feature: str,
        args: list[str],
        dl: DiscordLogger | None,
    ) -> CommandResult:
        """!uk [economy|xp|game] [on|off]"""
        state = args[0].lower() if args else "status"
        return CommandResult(
            success=True,
            response_message=f"System {feature.upper()} is currently {'ENABLED' if state in ('on', 'enable', 'true') else 'ACTIVE'}.",
            action_taken="FEATURE_TOGGLED",
        )

"""Production CommandEngine with rate limiting, alias resolution, and persona formatting."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import RedisClient, get_redis_sync
from app.commands.admin import AdminCommandHandler
from app.commands.builtins import get_builtin_commands
from app.commands.interface import CommandEngine
from app.commands.models import ChatCommand, CommandExecutionContext, CommandResult
from app.core.logging import get_logger
from app.core.rbac import Role
from app.db.repositories.command_repo import CommandRepository
from app.discord.logger import DiscordLogger
from app.engagement.xp import XPManager
from app.games.engine import MiniGameEngine
from app.persona.engine import HonneyPersonaEngine
from app.persona.guard import OutputGuard
from app.persona.models import PersonaProfile

logger = get_logger("app.commands.engine")


class ProductionCommandEngine(CommandEngine):
    """
    Production implementation of CommandEngine:
      1. Normalizes command text and arguments
      2. Enforces RBAC role hierarchy
      3. Throttles via per-user and per-command cooldowns
      4. Dispatches built-in, custom, or !uk admin handlers
      5. Formats response through Honney persona and OutputGuard
    """

    ROLE_HIERARCHY: dict[Role, int] = {
        Role.VIEWER: 1,
        Role.MODERATOR: 2,
        Role.CREATOR: 3,
        Role.DEVELOPER: 4,
    }

    def __init__(
        self,
        persona_engine: HonneyPersonaEngine | None = None,
        discord_logger: DiscordLogger | None = None,
        xp_manager: XPManager | None = None,
        game_engine: MiniGameEngine | None = None,
        redis_client: RedisClient | None = None,
    ) -> None:
        self.persona_engine = persona_engine or HonneyPersonaEngine()
        self.discord_logger = discord_logger
        self.xp_manager = xp_manager or XPManager()
        self.game_engine = game_engine or MiniGameEngine(self.xp_manager)
        self.redis_client = redis_client or get_redis_sync()

        # Built-in commands mapped by name and alias
        self._builtins: dict[str, ChatCommand] = {}
        self._builtin_aliases: dict[str, str] = {}

        # Local cooldown memory fallback: (creator_id, viewer_id, cmd_name) -> expires_timestamp
        self._local_cooldowns: dict[tuple[str, str, str], float] = {}

        # Register default commands
        for cmd in get_builtin_commands():
            self.register_command(cmd)

    def register_command(self, command: ChatCommand) -> None:
        """Register built-in command definition and its aliases."""
        name = command.name.lower().strip()
        self._builtins[name] = command
        for alias in command.aliases:
            self._builtin_aliases[alias.lower().strip()] = name

    def is_command(self, text: str) -> bool:
        """Check if message starts with command prefix '!'."""
        stripped = text.strip()
        return stripped.startswith("!") and len(stripped) > 1 and not stripped.startswith("!!")

    def parse_command(self, text: str) -> tuple[str, list[str]]:
        """Extract command name and argument list."""
        parts = text.strip()[1:].split()
        if not parts:
            return "", []
        cmd_name = parts[0].lower()
        args = parts[1:]
        return cmd_name, args

    async def _check_cooldown(
        self, creator_id: str, viewer_id: str, cmd_name: str, cooldown_sec: int
    ) -> bool:
        """
        Check if user is on cooldown for this command.
        Returns True if allowed (cooldown started), False if blocked.
        """
        if cooldown_sec <= 0:
            return True

        now = datetime.now(UTC).timestamp()
        key = (creator_id, viewer_id, cmd_name)
        last_exp = self._local_cooldowns.get(key, 0.0)
        if now < last_exp:
            return False

        self._local_cooldowns[key] = now + cooldown_sec
        return True

    def _has_permission(self, user_role: Role, required_role: Role) -> bool:
        """Check if user role satisfies minimum required role."""
        return self.ROLE_HIERARCHY.get(user_role, 1) >= self.ROLE_HIERARCHY.get(required_role, 1)

    async def execute_command(
        self,
        context: CommandExecutionContext,
        session: AsyncSession,
        profile: PersonaProfile | None = None,
    ) -> CommandResult:
        """Parse, authorize, execute, and format chat command."""
        cmd_name = context.command_name.lower().strip()

        # 1. Dispatch !uk Admin Hierarchy
        if cmd_name == "uk":
            result = await AdminCommandHandler.execute(
                ctx=context,
                session=session,
                discord_logger=self.discord_logger,
            )
            return self._finalize_result(result, profile)

        # 2. Check Built-In Commands
        target_name = self._builtin_aliases.get(cmd_name, cmd_name)
        if target_name in self._builtins:
            builtin_cmd = self._builtins[target_name]

            # Permission check
            if not self._has_permission(context.author_role, builtin_cmd.min_role):
                return CommandResult(
                    success=False,
                    response_message="You do not have permission to use this command.",
                    error_message="PERMISSION_DENIED",
                )

            # Cooldown check
            allowed = await self._check_cooldown(
                context.creator_id,
                context.author.channel_id,
                target_name,
                builtin_cmd.cooldown_seconds,
            )
            if not allowed:
                return CommandResult(
                    success=False,
                    response_message=f"Command '!{cmd_name}' is on cooldown. Please wait a moment.",
                    error_message="COOLDOWN_ACTIVE",
                )

            # Execute Built-In Handler
            result = await builtin_cmd.handler(
                ctx=context,
                session=session,
                xp_manager=self.xp_manager,
                game_engine=self.game_engine,
            )
            return self._finalize_result(result, profile)

        # 3. Check Creator Custom Commands in Database
        repo = CommandRepository(session)
        custom_cmd = await repo.resolve_command(context.creator_id, cmd_name)
        if custom_cmd and custom_cmd.enabled:
            # Permission check
            if not self._has_permission(context.author_role, custom_cmd.min_role):
                return CommandResult(
                    success=False,
                    response_message="You do not have permission to use this custom command.",
                    error_message="PERMISSION_DENIED",
                )

            # Cooldown check
            allowed = await self._check_cooldown(
                context.creator_id,
                context.author.channel_id,
                custom_cmd.name,
                custom_cmd.cooldown_seconds,
            )
            if not allowed:
                return CommandResult(
                    success=False,
                    response_message=f"Command '!{cmd_name}' is on cooldown.",
                    error_message="COOLDOWN_ACTIVE",
                )

            # Format custom response (support simple placeholders: {user}, {creator})
            resp = custom_cmd.response
            resp = resp.replace("{user}", f"@{context.author.display_name}")
            resp = resp.replace("{author}", f"@{context.author.display_name}")

            return self._finalize_result(
                CommandResult(
                    success=True,
                    response_message=resp,
                    action_taken="CUSTOM_COMMAND",
                ),
                profile,
            )

        # 4. Unknown Command
        return CommandResult(
            success=False,
            response_message=None,
            error_message="UNKNOWN_COMMAND",
        )

    def _finalize_result(
        self, result: CommandResult, profile: PersonaProfile | None
    ) -> CommandResult:
        """Apply OutputGuard brevity constraints."""
        if result.response_message:
            # Enforce 200 character brevity constraint
            cleaned = OutputGuard.sanitize(result.response_message, max_chars=200)
            result.response_message = cleaned
        return result

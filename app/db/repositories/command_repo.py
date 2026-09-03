"""Repository for CustomCommand and CommandAlias entities."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import Role
from app.db.models.custom_command import CommandAlias, CustomCommand


class CommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, creator_id: str, name: str) -> CustomCommand | None:
        """Find custom command by normalized lowercase name."""
        stmt = (
            select(CustomCommand)
            .where(
                CustomCommand.creator_id == creator_id,
                CustomCommand.name == name.lower().strip(),
            )
            .options(selectinload(CustomCommand.aliases))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_alias(self, creator_id: str, alias: str) -> CustomCommand | None:
        """Find custom command target through an alias."""
        stmt = (
            select(CustomCommand)
            .join(CommandAlias, CommandAlias.target_command_id == CustomCommand.id)
            .where(
                CommandAlias.creator_id == creator_id,
                CommandAlias.alias == alias.lower().strip(),
            )
            .options(selectinload(CustomCommand.aliases))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_command(self, creator_id: str, name_or_alias: str) -> CustomCommand | None:
        """Resolve command by name directly or via alias fallback."""
        cmd = await self.get_by_name(creator_id, name_or_alias)
        if cmd:
            return cmd
        return await self.get_by_alias(creator_id, name_or_alias)

    async def list_for_creator(self, creator_id: str) -> list[CustomCommand]:
        """List all custom commands configured for a creator."""
        stmt = (
            select(CustomCommand)
            .where(CustomCommand.creator_id == creator_id)
            .options(selectinload(CustomCommand.aliases))
            .order_by(CustomCommand.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_command(
        self,
        creator_id: str,
        name: str,
        response: str,
        min_role: Role = Role.VIEWER,
        cooldown_seconds: int = 5,
        enabled: bool = True,
    ) -> CustomCommand:
        """Create a new creator custom command."""
        cmd = CustomCommand(
            creator_id=creator_id,
            name=name.lower().strip(),
            response=response,
            min_role=min_role,
            cooldown_seconds=cooldown_seconds,
            enabled=enabled,
        )
        self.session.add(cmd)
        await self.session.flush()
        return cmd

    async def update_command(
        self,
        command: CustomCommand,
        response: str | None = None,
        min_role: Role | None = None,
        cooldown_seconds: int | None = None,
        enabled: bool | None = None,
    ) -> CustomCommand:
        """Update properties of an existing command."""
        if response is not None:
            command.response = response
        if min_role is not None:
            command.min_role = min_role
        if cooldown_seconds is not None:
            command.cooldown_seconds = cooldown_seconds
        if enabled is not None:
            command.enabled = enabled
        await self.session.flush()
        return command

    async def delete_command(self, creator_id: str, name: str) -> bool:
        """Delete custom command by name."""
        cmd = await self.get_by_name(creator_id, name)
        if not cmd:
            return False
        await self.session.delete(cmd)
        await self.session.flush()
        return True

    async def add_alias(self, creator_id: str, command_id: str, alias: str) -> CommandAlias:
        """Add alias mapping to custom command."""
        alias_obj = CommandAlias(
            creator_id=creator_id,
            target_command_id=command_id,
            alias=alias.lower().strip(),
        )
        self.session.add(alias_obj)
        await self.session.flush()
        return alias_obj

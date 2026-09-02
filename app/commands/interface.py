"""Command Engine abstract interface."""

from abc import ABC, abstractmethod

from app.commands.models import ChatCommand, CommandExecutionContext, CommandResult


class CommandEngine(ABC):
    """Abstract interface for parsing and executing chat commands."""

    @abstractmethod
    def register_command(self, command: ChatCommand) -> None:
        """Register a new command definition."""
        pass

    @abstractmethod
    async def execute_command(self, context: CommandExecutionContext) -> CommandResult:
        """Parse arguments, check permissions and cooldowns, and execute command."""
        pass

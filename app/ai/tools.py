"""Application-controlled tools for LLM tool-calling authorization."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.models import ToolCallRequest, ToolDefinition
from app.core.logging import get_logger

logger = get_logger("app.ai.tools")


class ApplicationToolRegistry:
    """
    Allowlist of application-authorized tools that LLMs may request.
    Strictly forbids raw database access, arbitrary HTTP, or shell commands.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in allowed tools."""
        self.register(
            ToolDefinition(
                name="get_stream_status",
                description="Get current status, viewer count, and active phase of the stream.",
                parameters={
                    "type": "object",
                    "properties": {
                        "stream_session_id": {"type": "string"},
                    },
                    "required": ["stream_session_id"],
                },
            ),
            self._handle_get_stream_status,
        )

        self.register(
            ToolDefinition(
                name="lookup_user_trust",
                description="Check community trust score and participation history for a chat viewer.",
                parameters={
                    "type": "object",
                    "properties": {
                        "creator_id": {"type": "string"},
                        "viewer_channel_id": {"type": "string"},
                    },
                    "required": ["creator_id", "viewer_channel_id"],
                },
            ),
            self._handle_lookup_user_trust,
        )

        self.register(
            ToolDefinition(
                name="get_creator_preferences",
                description="Lookup creator's persona sliders, stream guidelines, and rules.",
                parameters={
                    "type": "object",
                    "properties": {
                        "creator_id": {"type": "string"},
                    },
                    "required": ["creator_id"],
                },
            ),
            self._handle_get_creator_preferences,
        )

    def register(
        self,
        tool_def: ToolDefinition,
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        """Register an authorized tool and its handler."""
        self._tools[tool_def.name] = tool_def
        self._handlers[tool_def.name] = handler

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Return schema list of allowlisted tools for LLM prompts."""
        return list(self._tools.values())

    async def execute_tool_call(self, tool_call: ToolCallRequest) -> dict[str, Any]:
        """Validate allowlist and execute tool with parameters."""
        if tool_call.function_name not in self._handlers:
            logger.warning(f"Rejected unauthorized tool call: '{tool_call.function_name}'")
            return {"error": f"Tool '{tool_call.function_name}' is not authorized or allowlisted."}

        handler = self._handlers[tool_call.function_name]
        try:
            return await handler(tool_call.arguments)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_call.function_name}': {e}")
            return {"error": str(e)}

    # Built-in handlers
    async def _handle_get_stream_status(self, args: dict[str, Any]) -> dict[str, Any]:
        session_id = args.get("stream_session_id", "")
        return {
            "stream_session_id": session_id,
            "status": "RUNNING",
            "is_live": True,
        }

    async def _handle_lookup_user_trust(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "creator_id": args.get("creator_id", ""),
            "viewer_channel_id": args.get("viewer_channel_id", ""),
            "trust_score": 50,
            "standing": "NORMAL",
        }

    async def _handle_get_creator_preferences(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "creator_id": args.get("creator_id", ""),
            "persona": "CO_HOST",
            "moderation_strictness": "BALANCED",
        }


_global_tool_registry: ApplicationToolRegistry | None = None


def get_tool_registry() -> ApplicationToolRegistry:
    """Return singleton ApplicationToolRegistry."""
    global _global_tool_registry
    if _global_tool_registry is None:
        _global_tool_registry = ApplicationToolRegistry()
    return _global_tool_registry

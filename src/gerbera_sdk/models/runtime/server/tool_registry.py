from dataclasses import dataclass
from typing import Any, Callable

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from gerbera_sdk.events.reactions.reaction_executor import ReactionActionRegistry


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    tool_function: Callable[..., Any]
    annotations: ToolAnnotations
    meta: dict[str, Any] | None = None


@dataclass
class McpToolRegistry:
    app: FastMCP
    actions: ReactionActionRegistry

    def register(self, tool: ToolDefinition) -> None:
        if tool.annotations.readOnlyHint is False and tool.name not in {
            "create_reaction", "delete_reaction", "list_reactions",
        }:
            self.actions.register(tool.name, tool.tool_function)
        self.app.tool(
            name=tool.name,
            description=tool.description,
            annotations=tool.annotations,
            meta=tool.meta,
        )(tool.tool_function)

from dataclasses import dataclass
from typing import Any, Callable

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry


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
    actions: ReactionToolRegistry

    def register(self, tool: ToolDefinition) -> None:
        self.actions.register(tool.name, tool.tool_function, tool.annotations)
        self.app.tool(
            name=tool.name,
            description=tool.description,
            annotations=tool.annotations,
            meta=tool.meta,
        )(tool.tool_function)

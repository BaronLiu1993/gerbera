from dataclasses import dataclass
from functools import cached_property
from typing import Any

from gerbera_harness.tools.base import ToolSpec
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sources import CompositeToolSource, LocalToolSource, McpToolSource


@dataclass
class ToolClient:
    mcp_url: str
    local_tool_registry: LocalToolRegistry

    @cached_property
    def source(self) -> CompositeToolSource:
        return CompositeToolSource((LocalToolSource(self.local_tool_registry), McpToolSource(self.mcp_url)))

    async def list_tools(self) -> list[ToolSpec]:
        return await self.source.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self.source.call_tool(name, arguments)

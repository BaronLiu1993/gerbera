from dataclasses import dataclass
from typing import Any

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.tools.base import ToolSpec
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class ToolClient:
    mcp_url: str
    local_tool_registry: LocalToolRegistry

    async def list_tools(self) -> list[ToolSpec]:
        local_tools = self.local_tool_registry.list_tools()

        async with MCPClient(self.mcp_url) as mcp_client:
            mcp_tools = await mcp_client.list_tools()

        return [
            *local_tools,
            *[
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema,
                    read_only=(
                        tool.annotations is not None
                        and tool.annotations.readOnlyHint is True
                    ),
                )
                for tool in mcp_tools
            ],
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        if self.local_tool_registry.has(name):
            return await self.local_tool_registry.call_tool(name, arguments)

        async with MCPClient(self.mcp_url) as mcp_client:
            tools = await mcp_client.list_tools()
            allowed_tool_names = frozenset(tool.name for tool in tools)
            return await mcp_client.call_tool(
                name,
                arguments,
                allowed_tool_names,
            )

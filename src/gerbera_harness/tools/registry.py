from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.tools.base import LocalTool, ToolSpec


@dataclass
class LocalToolRegistry:
    tools: dict[str, LocalTool] = field(default_factory=dict)

    def register(self, tool: LocalTool) -> None:
        name = tool.spec.name
        if name in self.tools:
            raise ValueError(f"Local tool is already registered: {name}")
        self.tools[name] = tool

    def has(self, name: str) -> bool:
        return name in self.tools

    def list_tools(self) -> list[ToolSpec]:
        return [tool.spec for tool in self.tools.values()]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"Local tool is not registered: {name}")
        return await tool.call(arguments)

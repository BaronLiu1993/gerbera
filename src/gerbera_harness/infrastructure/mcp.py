from dataclasses import dataclass
from functools import cached_property
from typing import Any, ClassVar, Iterable, Protocol
from urllib.parse import urlsplit

from fastmcp import Client
from mcp.types import Tool


class MCPToolParameter(Protocol):
    tool_parameter: str
    value: Any


@dataclass
class MCPClient:
    mcp_url: str
    instances: ClassVar[dict[str, "MCPClient"]] = {}

    def __new__(cls, mcp_url: str):
        cls.validate_url(mcp_url)
        if mcp_url not in cls.instances:
            cls.instances[mcp_url] = super().__new__(cls)
        return cls.instances[mcp_url]

    @staticmethod
    def validate_url(mcp_url: str) -> None:
        parsed_url = urlsplit(mcp_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("MCP URL must use HTTP or HTTPS")

    @cached_property
    def client(self) -> Client:
        return Client(self.mcp_url)

    async def __aenter__(self) -> "MCPClient":
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.client.__aexit__(exc_type, exc, traceback)

    async def list_tools(self) -> list[Tool]:
        return await self.client.list_tools()

    @staticmethod
    def build_arguments(
        parameters: Iterable[MCPToolParameter],
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {}

        for parameter in parameters:
            if parameter.tool_parameter in arguments:
                raise ValueError(
                    "Duplicate MCP tool parameter: "
                    f"{parameter.tool_parameter}"
                )

            arguments[parameter.tool_parameter] = parameter.value

        return arguments

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        allowed_tool_names: frozenset[str],
    ) -> Any:
        if name not in allowed_tool_names:
            raise ValueError(f"MCP tool is not allowed: {name}")
        result = await self.client.call_tool(name, arguments)
        return result.data

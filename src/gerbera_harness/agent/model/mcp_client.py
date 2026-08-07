from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol
from urllib.parse import urlsplit

from fastmcp import Client
from mcp.types import Tool


class _MCPToolParameter(Protocol):
    tool_parameter: str
    value: Any


@dataclass
class MCPClient:
    mcp_url: str
    _client: Client | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        parsed_url = urlsplit(self.mcp_url)
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise ValueError("MCP URL must use HTTPS")

    async def __aenter__(self) -> "MCPClient":
        self._client = Client(self.mcp_url)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        client = self._require_client()
        try:
            await client.__aexit__(exc_type, exc, traceback)
        finally:
            self._client = None

    async def list_tools(self) -> list[Tool]:
        return await self._require_client().list_tools()

    @staticmethod
    def build_arguments(
        parameters: Iterable[_MCPToolParameter],
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
        *,
        structured: bool = False,
    ) -> Any:
        if name not in allowed_tool_names:
            raise ValueError(f"MCP tool is not allowed: {name}")

        result = await self._require_client().call_tool(name, arguments)

        if result.is_error:
            raise RuntimeError(f"MCP tool {name!r} failed: {result.content}")

        if structured:
            return result.structured_content

        return result.data

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("MCP client is not connected")
        return self._client

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from fastmcp import Client
from mcp.types import CallToolResult, Tool


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

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> CallToolResult:
        return await self._require_client().call_tool(name, arguments)

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("MCP client is not connected")
        return self._client

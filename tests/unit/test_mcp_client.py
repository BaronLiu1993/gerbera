import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.harness.agent.model.mcp_client import MCPClient


class FakeFastMCPClient:
    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def list_tools(self) -> list:
        return [SimpleNamespace(name="read_temperature")]

    async def call_tool(self, name: str, arguments=None):
        return SimpleNamespace(data={"value": "21.5"})


def test_mcp_client_lists_and_calls_hardware_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_sdk.harness.agent.model.mcp_client.Client",
        FakeFastMCPClient,
    )

    async def use_client() -> None:
        async with MCPClient("https://hardware.example.com/mcp") as client:
            tools = await client.list_tools()
            result = await client.call_tool("read_temperature")

            assert [tool.name for tool in tools] == ["read_temperature"]
            assert result.data == {"value": "21.5"}

    asyncio.run(use_client())


def test_mcp_client_requires_an_active_connection() -> None:
    client = MCPClient("https://hardware.example.com/mcp")

    with pytest.raises(RuntimeError, match="not connected"):
        asyncio.run(client.list_tools())


@pytest.mark.parametrize(
    "url",
    [
        "http://hardware.example.com/mcp",
        "hardware.example.com/mcp",
        "https:///mcp",
    ],
)
def test_mcp_client_rejects_non_https_urls(url: str) -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        MCPClient(url)

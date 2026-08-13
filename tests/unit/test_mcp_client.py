import asyncio
from types import SimpleNamespace

import pytest

from gerbera_harness.infrastructure.mcp import MCPClient


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
        return SimpleNamespace(
            is_error=False,
            content=[],
            data={"value": "21.5"},
        )


def test_mcp_client_lists_and_calls_hardware_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.mcp.Client",
        FakeFastMCPClient,
    )

    async def use_client() -> None:
        async with MCPClient("https://hardware.example.com/mcp") as client:
            tools = await client.list_tools()
            result = await client.call_tool(
                "read_temperature",
                {},
                frozenset({"read_temperature"}),
            )

            assert [tool.name for tool in tools] == ["read_temperature"]
            assert result == {"value": "21.5"}

    asyncio.run(use_client())


def test_mcp_client_allows_http_urls(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.mcp.Client",
        FakeFastMCPClient,
    )

    client = MCPClient("http://127.0.0.1:8001/mcp")

    assert client.client.url == "http://127.0.0.1:8001/mcp"


def test_mcp_client_reuses_instance_for_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.mcp.Client",
        FakeFastMCPClient,
    )

    first_client = MCPClient("https://hardware.example.com/mcp")
    second_client = MCPClient("https://hardware.example.com/mcp")

    assert first_client is second_client


def test_mcp_client_builds_tool_arguments() -> None:
    parameters = [
        SimpleNamespace(tool_parameter="enabled", value=True),
        SimpleNamespace(tool_parameter="sample_rate", value=10),
    ]

    assert MCPClient.build_arguments(parameters) == {
        "enabled": True,
        "sample_rate": 10,
    }


def test_mcp_client_rejects_duplicate_tool_arguments() -> None:
    parameters = [
        SimpleNamespace(tool_parameter="enabled", value=True),
        SimpleNamespace(tool_parameter="enabled", value=False),
    ]

    with pytest.raises(ValueError, match="Duplicate MCP tool parameter"):
        MCPClient.build_arguments(parameters)


def test_mcp_client_rejects_disallowed_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.mcp.Client",
        FakeFastMCPClient,
    )

    async def use_client() -> None:
        async with MCPClient("https://hardware.example.com/mcp") as client:
            with pytest.raises(ValueError, match="MCP tool is not allowed"):
                await client.call_tool(
                    "set_temperature",
                    {"value": 25},
                    frozenset({"read_temperature"}),
                )

    asyncio.run(use_client())


def test_mcp_client_raises_when_tool_call_fails(monkeypatch) -> None:
    async def fail_tool_call(self, name: str, arguments=None):
        return SimpleNamespace(
            is_error=True,
            content=[SimpleNamespace(text="tool failed")],
            data=None,
        )

    monkeypatch.setattr(FakeFastMCPClient, "call_tool", fail_tool_call)
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.mcp.Client",
        FakeFastMCPClient,
    )

    async def use_client() -> None:
        async with MCPClient("https://hardware.example.com/mcp") as client:
            with pytest.raises(
                RuntimeError,
                match="'read_temperature' failed",
            ):
                await client.call_tool(
                    "read_temperature",
                    {},
                    frozenset({"read_temperature"}),
                )

    asyncio.run(use_client())


@pytest.mark.parametrize(
    "url",
    [
        "hardware.example.com/mcp",
        "https:///mcp",
        "ftp://hardware.example.com/mcp",
    ],
)
def test_mcp_client_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
        MCPClient(url)

import asyncio
from types import SimpleNamespace

from gerbera_harness.agent.driver.main_loop.processes.initialisation_process import (
    InitialisationProcess,
)


def test_generate_agent_context_formats_markdown() -> None:
    process = InitialisationProcess("https://hardware.example.com/mcp")

    context = process.generate_agent_context(
        user_prompt="Test whether heating raises temperature.",
        hardware_tools=[
            {
                "name": "read_temperature",
                "description": "Read the temperature sensor.",
                "schema": {"type": "object"},
            }
        ],
        sources={"https://example.com/method": "Methodology details."},
    )

    assert context.startswith("# Experiment Context")
    assert "## Objective" in context
    assert "### read_temperature" in context
    assert '"type": "object"' in context
    assert "### https://example.com/method" in context
    assert "Methodology details." in context


def test_run_inspects_hardware_then_builds_context(monkeypatch) -> None:
    calls = []

    class FakeMCPClient:
        def __init__(self, mcp_url: str) -> None:
            assert mcp_url == "https://hardware.example.com/mcp"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            pass

        async def list_tools(self) -> list:
            calls.append("inspect_hardware")
            return [
                SimpleNamespace(
                    name="read_temperature",
                    description="Read the temperature sensor.",
                    inputSchema={"type": "object"},
                ),
            ]

    monkeypatch.setattr(
        "gerbera_harness.agent.driver.main_loop.processes.initialisation_process.MCPClient",
        FakeMCPClient,
    )
    process = InitialisationProcess(
        "https://hardware.example.com/mcp",
        ["https://example.com/method"],
    )
    async def fetch_url(url: str) -> str:
        calls.append("fetch_url")
        return "Methodology details."

    monkeypatch.setattr(process, "fetch_url", fetch_url)

    context = asyncio.run(process.run("Test the heater."))

    assert calls == ["inspect_hardware", "fetch_url"]
    assert "# Experiment Context" in context
    assert "Test the heater." in context


def test_fetch_url_uses_async_http_client(monkeypatch) -> None:
    requested_urls = []

    class FakeResponse:
        text = "Methodology details."

        def raise_for_status(self) -> None:
            pass

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 10.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            pass

        async def get(self, url: str) -> FakeResponse:
            requested_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(
        "gerbera_harness.agent.driver.main_loop.processes."
        "initialisation_process.httpx.AsyncClient",
        FakeAsyncClient,
    )
    process = InitialisationProcess("https://hardware.example.com/mcp")

    result = asyncio.run(process.fetch_url("https://example.com/method"))

    assert result == "Methodology details."
    assert requested_urls == ["https://example.com/method"]

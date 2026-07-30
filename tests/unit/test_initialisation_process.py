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
        event_catalog={
            "STREAM": {
                "board-1": {
                    "temperature": {
                        "event_type": "STREAM",
                        "microcontroller_id": "board-1",
                        "event_name": "temperature",
                    }
                }
            }
        },
    )

    assert context.startswith("# Experiment Context")
    assert "## Objective" in context
    assert "## Available Rule Events" in context
    assert '"microcontroller_id": "board-1"' in context
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
                SimpleNamespace(
                    name="list_rule_events",
                    description="List rule events.",
                    inputSchema={"type": "object"},
                ),
            ]

        async def call_tool(
            self,
            name,
            arguments,
            allowed_tool_names,
            *,
            structured=False,
        ):
            assert name == "list_rule_events"
            assert arguments == {}
            assert name in allowed_tool_names
            assert structured is True
            calls.append("list_rule_events")
            return {
                "STREAM": {
                    "board-1": {
                        "temperature": {
                            "event_type": "STREAM",
                            "microcontroller_id": "board-1",
                            "event_name": "temperature",
                        }
                    }
                }
            }

    monkeypatch.setattr(
        "gerbera_harness.agent.driver.main_loop.processes.initialisation_process.MCPClient",
        FakeMCPClient,
    )
    process = InitialisationProcess(
        "https://hardware.example.com/mcp",
        ["https://example.com/method"],
    )
    monkeypatch.setattr(
        process,
        "fetch_url",
        lambda url: calls.append("fetch_url") or "Methodology details.",
    )

    context = asyncio.run(process.run("Test the heater."))

    assert calls == ["inspect_hardware", "list_rule_events", "fetch_url"]
    assert process.available_tool_names == frozenset(
        {"read_temperature", "list_rule_events"}
    )
    assert "# Experiment Context" in context
    assert "Test the heater." in context
    assert '"event_name": "temperature"' in context

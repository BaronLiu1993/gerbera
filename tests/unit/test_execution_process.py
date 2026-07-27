import asyncio
from types import SimpleNamespace

import pytest

from gerbera_sdk.harness.agent.experiments.states.processes import (
    execution_process,
)
from gerbera_sdk.harness.agent.experiments.states.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)


def parameter(variable: str, value, parameter_type: str) -> dict:
    return {
        "variable": variable,
        "value": value,
        "unit": None,
        "type": parameter_type,
    }


def discrete_action(
    tool_name: str = "set_motor",
) -> DiscreteExecuteSchema:
    return DiscreteExecuteSchema.model_validate(
        {
            "description": "Set the motor speed.",
            "action_type": "execute",
            "execution_type": "discrete",
            "start_offset_seconds": 0,
            "dependent_variables": ["motor_speed"],
            "independent_variables": ["requested_speed"],
            "forward_tool_call": tool_name,
            "params": [parameter("speed", 10, "int")],
        }
    )


def continuous_action() -> ContinuousExecuteSchema:
    return ContinuousExecuteSchema.model_validate(
        {
            "description": "Collect sensor readings.",
            "action_type": "execute",
            "execution_type": "continuous",
            "start_offset_seconds": 0,
            "duration_seconds": 0.001,
            "dependent_variables": ["sensor_value"],
            "independent_variables": ["sensor_state"],
            "forward_tool_call": "start_sensor",
            "reverse_tool_call": "stop_sensor",
            "forward_tool_call_params": [
                parameter("enabled", True, "bool")
            ],
            "reverse_tool_call_params": [
                parameter("enabled", False, "bool")
            ],
        }
    )


class FakeMCPClient:
    calls: list[tuple[str, dict]] = []
    failing_tools: set[str] = set()

    def __init__(self, mcp_url: str) -> None:
        assert mcp_url == "https://hardware.example.com/mcp"

    async def __aenter__(self):
        type(self).calls = []
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def list_tools(self) -> list:
        return [
            SimpleNamespace(name="set_motor"),
            SimpleNamespace(name="start_sensor"),
            SimpleNamespace(name="stop_sensor"),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        allowed_tool_names: frozenset[str],
    ):
        if name not in allowed_tool_names:
            raise ValueError(f"MCP tool is not allowed: {name}")

        type(self).calls.append((name, arguments))
        if name in type(self).failing_tools:
            raise RuntimeError(f"MCP tool {name!r} failed: tool failed")

        return {"tool": name}


@pytest.fixture(autouse=True)
def fake_mcp_client(monkeypatch):
    FakeMCPClient.failing_tools = set()
    monkeypatch.setattr(execution_process, "MCPClient", FakeMCPClient)


def test_execution_process_calls_discrete_mcp_tool() -> None:
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[discrete_action()],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls == [("set_motor", {"speed": 10})]
    assert result is None


def test_execution_process_stops_continuous_action() -> None:
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[continuous_action()],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls == [
        ("start_sensor", {"enabled": True}),
        ("stop_sensor", {"enabled": False}),
    ]
    assert result is None


def test_execution_process_rejects_unknown_tool() -> None:
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[discrete_action("unknown_tool")],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    with pytest.raises(RuntimeError, match="Execution group 0 failed"):
        asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls == []


def test_execution_process_stops_continuous_action_on_group_failure() -> None:
    FakeMCPClient.failing_tools = {"set_motor"}
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[continuous_action(), discrete_action()],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    with pytest.raises(RuntimeError, match="Execution group 0 failed"):
        asyncio.run(process.run_workflow())

    assert ("start_sensor", {"enabled": True}) in FakeMCPClient.calls
    assert ("set_motor", {"speed": 10}) in FakeMCPClient.calls
    assert ("stop_sensor", {"enabled": False}) in FakeMCPClient.calls

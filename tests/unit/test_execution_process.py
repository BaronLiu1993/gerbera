import asyncio
from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.main_loop.processes import (
    execution_process,
)
from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    RuleCreationSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
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
            "emitted_event_keys": [
                {
                    "event_type": "STREAM",
                    "microcontroller_id": "board-1",
                    "event_name": "sensor_value",
                }
            ],
        }
    )


def agent_action() -> AgentExecuteSchema:
    return AgentExecuteSchema.model_validate(
        {
            "description": "Approach the detected block.",
            "action_type": "execute",
            "execution_type": "agent",
            "start_offset_seconds": 0,
            "goal": "Move within grasping range of the block.",
            "completion_criteria": "The block is centered and within reach.",
            "input_event_keys": [
                {
                    "event_type": "VISION",
                    "microcontroller_id": "camera-1",
                    "event_name": "block_detected",
                }
            ],
            "allowed_tool_calls": ["set_motor"],
            "max_iterations": 10,
            "timeout_seconds": 30,
        }
    )


def rule_creation_action() -> RuleCreationSchema:
    return RuleCreationSchema.model_validate(
        {
            "description": "Watch for excessive temperature.",
            "action_type": "execute",
            "execution_type": "rule",
            "create_tool_call": "insert_rule",
            "delete_tool_call": "delete_rule",
            "event_key": {
                "event_type": "STREAM",
                "microcontroller_id": "board-1",
                "event_name": "temperature",
            },
            "callable": "return None",
            "operator": "greater_than",
            "expected": 20,
            "trigger_mode": "repeat",
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
            SimpleNamespace(name="insert_rule"),
            SimpleNamespace(name="delete_rule"),
        ]

    @staticmethod
    def build_arguments(parameters) -> dict:
        return {
            parameter.variable: parameter.value
            for parameter in parameters
        }

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


def test_execution_process_reports_unimplemented_agent_loop() -> None:
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[agent_action()],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    with pytest.raises(RuntimeError, match="Execution group 0 failed") as exc:
        asyncio.run(process.run_workflow())

    assert isinstance(exc.value.__cause__, ExceptionGroup)
    assert isinstance(exc.value.__cause__.exceptions[0], NotImplementedError)


def test_execution_process_creates_rule_before_action_and_deletes_it() -> None:
    group = ExecuteActionGroupSchema(
        action_type="execute",
        actions=[discrete_action(), rule_creation_action()],
    )
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    event_key = {
        "event_type": "STREAM",
        "microcontroller_id": "board-1",
        "event_name": "temperature",
    }
    assert FakeMCPClient.calls == [
        (
            "insert_rule",
            {
                **event_key,
                "expected_value": 20.0,
                "operator": "greater_than",
                "callback_body": "return None",
                "trigger_mode": "repeat",
            },
        ),
        ("set_motor", {"speed": 10}),
        ("delete_rule", event_key),
    ]
    assert result is None


def test_execution_process_deletes_rule_when_later_group_fails() -> None:
    FakeMCPClient.failing_tools = {"set_motor"}
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                action_type="execute",
                actions=[rule_creation_action()],
            ),
            ExecuteActionGroupSchema(
                action_type="execute",
                actions=[discrete_action()],
            ),
        ],
    )

    with pytest.raises(RuntimeError, match="Execution group 1 failed"):
        asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls[-1] == (
        "delete_rule",
        {
            "event_type": "STREAM",
            "microcontroller_id": "board-1",
            "event_name": "temperature",
        },
    )


def test_execution_process_rejects_rule_after_first_group() -> None:
    process = ExecutionProcess(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                action_type="execute",
                actions=[discrete_action()],
            ),
            ExecuteActionGroupSchema(
                action_type="execute",
                actions=[rule_creation_action()],
            ),
        ],
    )

    with pytest.raises(ValueError, match="first execute group"):
        asyncio.run(process.run_workflow())


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

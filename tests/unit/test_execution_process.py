import asyncio
from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.main_loop.processes import (
    execution_process,
)
from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
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
            "action_type": "execute",
            "execution_type": "agent",
            "goal": "Move within grasping range of the block.",
            "completion_criteria": "The block is centered and within reach.",
            "max_turns": 10,
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


async def reject_agent(group_index, action) -> ExecuteDecisionEnum:
    return ExecuteDecisionEnum.REJECTED


def make_execution_process(**kwargs) -> ExecutionProcess:
    kwargs.setdefault("agent_executor", reject_agent)
    kwargs.setdefault("on_group_started", lambda index, group: None)
    kwargs.setdefault("on_group_completed", lambda index, group: None)
    return ExecutionProcess(**kwargs)


def test_execution_process_calls_discrete_mcp_tool() -> None:
    group = ExecuteActionGroupSchema(
        goal="Set the motor speed.",
        action_type="execute",
        actions=[discrete_action()],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls == [("set_motor", {"speed": 10})]
    assert result is ExecuteDecisionEnum.ACCEPTED
    assert process.tool_events == [
        {
            "position": 0,
            "execution_type": "discrete",
            "call_type": "forward",
            "tool_name": "set_motor",
            "arguments": {"speed": 10},
            "status": "success",
            "result": {"tool": "set_motor"},
        }
    ]


def test_execution_process_stops_continuous_action() -> None:
    group = ExecuteActionGroupSchema(
        goal="Collect sensor readings.",
        action_type="execute",
        actions=[continuous_action()],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert FakeMCPClient.calls == [
        ("start_sensor", {"enabled": True}),
        ("stop_sensor", {"enabled": False}),
    ]
    assert result is ExecuteDecisionEnum.ACCEPTED


def test_execution_process_rejects_agent_actions() -> None:
    group = ExecuteActionGroupSchema(
        goal="Approach the detected block.",
        action_type="execute",
        actions=[agent_action()],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.REJECTED


def test_execution_process_coordinates_all_groups_with_agent_executor() -> None:
    started_groups: list[int] = []
    completed_groups: list[int] = []
    executed_agents: list[tuple[int, AgentExecuteSchema]] = []

    async def execute_agent(
        group_index: int,
        action: AgentExecuteSchema,
    ) -> ExecuteDecisionEnum:
        executed_agents.append((group_index, action))
        return ExecuteDecisionEnum.ACCEPTED

    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                goal="Install the safety rule.",
                action_type="execute",
                actions=[rule_creation_action()],
            ),
            ExecuteActionGroupSchema(
                goal="Approach the block.",
                action_type="execute",
                actions=[agent_action()],
            ),
            ExecuteActionGroupSchema(
                goal="Set the motor speed.",
                action_type="execute",
                actions=[discrete_action()],
            ),
        ],
        agent_executor=execute_agent,
        on_group_started=lambda index, group: started_groups.append(index),
        on_group_completed=lambda index, group: completed_groups.append(
            index
        ),
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.ACCEPTED
    assert started_groups == [0, 1, 2]
    assert completed_groups == [0, 1, 2]
    assert executed_agents == [(1, process.actions_list[1].actions[0])]
    assert [call[0] for call in FakeMCPClient.calls] == [
        "insert_rule",
        "set_motor",
        "delete_rule",
    ]


def test_execution_process_stops_workflow_after_failed_agent_group() -> None:
    attempts = 0

    async def execute_agent(
        group_index: int,
        action: AgentExecuteSchema,
    ) -> ExecuteDecisionEnum:
        nonlocal attempts
        attempts += 1
        return ExecuteDecisionEnum.REJECTED

    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                goal="Approach the block.",
                action_type="execute",
                actions=[agent_action()],
            ),
            ExecuteActionGroupSchema(
                goal="Set the motor speed.",
                action_type="execute",
                actions=[discrete_action()],
            ),
        ],
        agent_executor=execute_agent,
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.REJECTED
    assert attempts == 3
    assert FakeMCPClient.calls == []


def test_execution_process_completes_task_after_retry() -> None:
    attempts = 0
    completed_groups = []

    async def execute_agent(
        group_index: int,
        action: AgentExecuteSchema,
    ) -> ExecuteDecisionEnum:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return ExecuteDecisionEnum.REJECTED
        return ExecuteDecisionEnum.ACCEPTED

    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                goal="Approach the block.",
                action_type="execute",
                actions=[agent_action()],
            )
        ],
        agent_executor=execute_agent,
        on_group_completed=lambda index, group: completed_groups.append(
            index
        ),
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.ACCEPTED
    assert attempts == 3
    assert completed_groups == [0]


def test_execution_process_creates_rule_before_action_and_deletes_it() -> None:
    group = ExecuteActionGroupSchema(
        goal="Set the motor speed safely.",
        action_type="execute",
        actions=[discrete_action(), rule_creation_action()],
    )
    process = make_execution_process(
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
    assert result is ExecuteDecisionEnum.ACCEPTED


def test_execution_process_deletes_rule_when_later_group_fails() -> None:
    FakeMCPClient.failing_tools = {"set_motor"}
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[
            ExecuteActionGroupSchema(
                goal="Install the safety rule.",
                action_type="execute",
                actions=[rule_creation_action()],
            ),
            ExecuteActionGroupSchema(
                goal="Set the motor speed.",
                action_type="execute",
                actions=[discrete_action()],
            ),
        ],
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.REJECTED
    assert FakeMCPClient.calls.count(("set_motor", {"speed": 10})) == 3

    assert FakeMCPClient.calls[-1] == (
        "delete_rule",
        {
            "event_type": "STREAM",
            "microcontroller_id": "board-1",
            "event_name": "temperature",
        },
    )


def test_execution_process_fails_when_rule_cleanup_fails() -> None:
    FakeMCPClient.failing_tools = {"delete_rule"}
    group = ExecuteActionGroupSchema(
        goal="Set the motor speed safely.",
        action_type="execute",
        actions=[rule_creation_action(), discrete_action()],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    with pytest.raises(RuntimeError, match="delete_rule"):
        asyncio.run(process.run_workflow())


def test_execution_process_rejects_unknown_tool() -> None:
    group = ExecuteActionGroupSchema(
        goal="Call an unavailable tool.",
        action_type="execute",
        actions=[discrete_action("unknown_tool")],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.REJECTED
    assert process.tool_events == []
    assert FakeMCPClient.calls == []


def test_execution_process_stops_continuous_action_on_group_failure() -> None:
    FakeMCPClient.failing_tools = {"set_motor"}
    group = ExecuteActionGroupSchema(
        goal="Collect readings while setting the motor speed.",
        action_type="execute",
        actions=[continuous_action(), discrete_action()],
    )
    process = make_execution_process(
        mcp_url="https://hardware.example.com/mcp",
        actions_list=[group],
    )

    result = asyncio.run(process.run_workflow())

    assert result is ExecuteDecisionEnum.REJECTED
    assert ("start_sensor", {"enabled": True}) in FakeMCPClient.calls
    assert ("set_motor", {"speed": 10}) in FakeMCPClient.calls
    assert ("stop_sensor", {"enabled": False}) in FakeMCPClient.calls

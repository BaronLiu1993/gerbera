import asyncio
import json
from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.agent.driver.subloop.schema.act import (
    ToolCallStatusEnum,
)
from gerbera_harness.agent_runtime.sub_loop import act_runtime
from gerbera_harness.agent_runtime.sub_loop.act_runtime import ActRuntime


def parameter(variable: str, value: object, parameter_type: str) -> dict:
    return {
        "variable": variable,
        "value": value,
        "unit": None,
        "type": parameter_type,
    }


def discrete_action() -> DiscreteExecuteSchema:
    return DiscreteExecuteSchema.model_validate(
        {
            "description": "Set the motor speed.",
            "action_type": "execute",
            "execution_type": "discrete",
            "start_offset_seconds": 0,
            "dependent_variables": ["motor_speed"],
            "independent_variables": ["requested_speed"],
            "forward_tool_call": "set_motor",
            "params": [parameter("speed", 10, "int")],
        }
    )


def continuous_action() -> ContinuousExecuteSchema:
    return ContinuousExecuteSchema.model_validate(
        {
            "description": "Run the motor briefly.",
            "action_type": "execute",
            "execution_type": "continuous",
            "start_offset_seconds": 0,
            "duration_seconds": 1,
            "dependent_variables": ["motor_position"],
            "independent_variables": ["motor_state"],
            "forward_tool_call": "start_motor",
            "reverse_tool_call": "stop_motor",
            "forward_tool_call_params": [
                parameter("enabled", True, "bool")
            ],
            "reverse_tool_call_params": [
                parameter("enabled", False, "bool")
            ],
            "emitted_event_keys": [],
        }
    )


class FakeMCPClient:
    calls: list[tuple[str, dict]] = []
    failing_tools: set[str] = set()
    slow_tools: set[str] = set()

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
            SimpleNamespace(name="start_motor"),
            SimpleNamespace(name="stop_motor"),
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
    ) -> dict[str, str]:
        if name not in allowed_tool_names:
            raise ValueError(f"MCP tool is not allowed: {name}")

        type(self).calls.append((name, arguments))
        if name in type(self).slow_tools:
            await asyncio.sleep(0.05)
        if name in type(self).failing_tools:
            raise RuntimeError(f"MCP tool {name!r} failed")

        return {"tool": name}


@pytest.fixture(autouse=True)
def fake_mcp_client(monkeypatch) -> None:
    FakeMCPClient.failing_tools = set()
    FakeMCPClient.slow_tools = set()
    monkeypatch.setattr(act_runtime, "MCPClient", FakeMCPClient)


def run_action(action, timeout_seconds: float = 1) -> tuple:
    messages = []
    tool_events = []
    runtime = ActRuntime(
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=timeout_seconds,
        messages=messages,
        tool_events=tool_events,
    )

    status = asyncio.run(runtime.run_action(action))
    events = [
        json.loads(message["content"])
        for message in messages
    ]
    return status, events, messages, tool_events


def test_act_runtime_records_success() -> None:
    status, events, messages, tool_events = run_action(discrete_action())

    assert status is ToolCallStatusEnum.SUCCESS
    assert events == [
        {
            "tool_name": "set_motor",
            "status": "success",
            "result": {"tool": "set_motor"},
            "call_type": "forward",
            "error_message": None,
        }
    ]
    assert messages[-1]["role"] == "user"
    assert tool_events[-1]["status"] == "success"


def test_act_runtime_records_failure_without_raising() -> None:
    FakeMCPClient.failing_tools = {"set_motor"}

    status, events, _, _ = run_action(discrete_action())

    assert status is ToolCallStatusEnum.FAILED
    assert events[0]["status"] == "failed"
    assert events[0]["call_type"] == "forward"
    assert "set_motor" in events[0]["error_message"]


def test_act_runtime_records_forward_and_reverse_calls() -> None:
    action = continuous_action().model_copy(
        update={"duration_seconds": 0}
    )

    status, events, _, _ = run_action(action)

    assert status is ToolCallStatusEnum.SUCCESS
    assert FakeMCPClient.calls == [
        ("start_motor", {"enabled": True}),
        ("stop_motor", {"enabled": False}),
    ]
    assert [event["call_type"] for event in events] == [
        "forward",
        "reverse",
    ]


def test_act_runtime_records_tool_call_timeout() -> None:
    FakeMCPClient.slow_tools = {"set_motor"}

    status, events, _, _ = run_action(
        discrete_action(), timeout_seconds=0.01
    )

    assert status is ToolCallStatusEnum.TIMED_OUT
    assert events[0]["status"] == "timed_out"
    assert events[0]["tool_name"] == "set_motor"


def test_act_runtime_stops_continuous_action_when_cancelled() -> None:
    messages = []
    tool_events = []
    runtime = ActRuntime(
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
        messages=messages,
        tool_events=tool_events,
    )

    async def cancel_action() -> None:
        task = asyncio.create_task(runtime.run_action(continuous_action()))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_action())

    assert FakeMCPClient.calls == [
        ("start_motor", {"enabled": True}),
        ("stop_motor", {"enabled": False}),
    ]

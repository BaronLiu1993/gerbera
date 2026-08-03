import asyncio

import pytest

from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcessResult,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
)
from gerbera_harness.agent_runtime.main_loop import execution_runtime
from gerbera_harness.agent_runtime.main_loop.execution_runtime import (
    ExecutionRuntime,
)
from gerbera_harness.memory import EventTypeEnum, Memory, TaskSchema


def current_task() -> TaskSchema:
    return TaskSchema.model_validate(
        {
            "status": "in_progress",
            "task": {
                "goal": "Set the motor speed to 10",
                "action_type": "execute",
                "actions": [
                    {
                        "description": "Set the motor speed",
                        "action_type": "execute",
                        "execution_type": "discrete",
                        "start_offset_seconds": 0,
                        "dependent_variables": ["motor_speed"],
                        "independent_variables": ["requested_speed"],
                        "forward_tool_call": "set_motor",
                        "params": [],
                    }
                ],
            },
        }
    )


class FakeExecutionProcess:
    instances: list["FakeExecutionProcess"] = []
    result = ExecutionProcessResult(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[],
    )

    def __init__(self, mcp_url: str, actions_list: list) -> None:
        self.mcp_url = mcp_url
        self.actions_list = actions_list
        type(self).instances.append(self)

    async def run_workflow(self) -> ExecutionProcessResult:
        return type(self).result


@pytest.fixture(autouse=True)
def fake_execution_process(monkeypatch) -> None:
    FakeExecutionProcess.instances = []
    FakeExecutionProcess.result = ExecutionProcessResult(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[],
    )
    monkeypatch.setattr(
        execution_runtime,
        "ExecutionProcess",
        FakeExecutionProcess,
    )


def runtime_memory() -> Memory:
    memory = Memory(goal="Test the motor")
    memory.tasks.append(current_task())
    return memory


def test_execution_runtime_runs_one_task_and_requests_review() -> None:
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert result.requested_next_state is LoopStateEnum.REVIEW
    assert len(FakeExecutionProcess.instances) == 1
    assert FakeExecutionProcess.instances[0].actions_list == [
        memory.get_current_task().task
    ]
    assert result.event.event_type is EventTypeEnum.EXECUTION_RESULT
    assert result.event.payload["decision"] == "accepted"
    assert result.event.payload["step_goal"] == (
        "Set the motor speed to 10"
    )
    assert memory.errors == []


def test_execution_runtime_records_failure_and_requests_review() -> None:
    FakeExecutionProcess.result = ExecutionProcessResult(
        decision=ExecuteDecisionEnum.FAILED,
        errors=[
            ExecuteErrorSchema(
                event_name="Set the motor speed to 10",
                event_type=ExecutionTypeEnum.DISCRETE,
                position=0,
                error="motor rejected command",
            )
        ],
    )
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.FAILED
    assert result.requested_next_state is LoopStateEnum.REVIEW
    assert result.event.payload["decision"] == "failed"
    assert result.event.payload["errors"] == ["motor rejected command"]
    assert memory.event_ledger == [result.event]
    assert memory.errors[0].error == "motor rejected command"


def test_execution_runtime_rejects_incomplete_deterministic_actions() -> None:
    FakeExecutionProcess.result = ExecutionProcessResult(
        decision=ExecuteDecisionEnum.FAILED,
        errors=[
            ExecuteErrorSchema(
                event_name="deterministic_actions",
                event_type=ExecutionTypeEnum.DISCRETE,
                position=0,
                error="Not all deterministic actions completed",
            )
        ],
    )
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.FAILED
    assert result.event.payload["errors"] == [
        "Not all deterministic actions completed"
    ]
    assert memory.errors[0].error == (
        "Not all deterministic actions completed"
    )

import asyncio
from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ExecutionTypeEnum as ActionExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
)
from gerbera_harness.agent_runtime.main_loop import execution_runtime
from gerbera_harness.agent_runtime.main_loop.execution_runtime import (
    ExecutionRuntime,
)
from gerbera_harness.agent_runtime.subagent_result import SubAgentResult
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


def test_execution_type_uses_one_enum_with_rule_support() -> None:
    assert ExecutionTypeEnum is ActionExecutionTypeEnum
    assert ExecutionTypeEnum.RULE.value == "rule"


def current_agent_task() -> TaskSchema:
    return TaskSchema.model_validate(
        {
            "status": "in_progress",
            "task": {
                "goal": "Center the block",
                "action_type": "execute",
                "actions": [
                    {
                        "action_type": "execute",
                        "execution_type": "agent",
                        "goal": "Center the block using camera feedback",
                        "completion_criteria": "The block is centered",
                        "max_turns": 7,
                        "timeout_seconds": 12.5,
                    }
                ],
            },
        }
    )


class FakeExecutionProcess:
    instances: list["FakeExecutionProcess"] = []
    result = ExecuteDecisionEnum.ACCEPTED
    errors: list[ExecuteErrorSchema] = []
    failure: Exception | None = None

    def __init__(
        self,
        mcp_url: str,
        actions_list: list,
        agent_executor=None,
        on_group_started=None,
    ) -> None:
        self.mcp_url = mcp_url
        self.actions_list = actions_list
        self.agent_executor = agent_executor
        self.on_group_started = on_group_started
        self.errors = list(type(self).errors)
        type(self).instances.append(self)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        if type(self).failure is not None:
            raise type(self).failure
        for group_index, group in enumerate(self.actions_list):
            if self.on_group_started is not None:
                self.on_group_started(group_index, group)
            action = group.actions[0]
            if action.execution_type == "agent":
                decision, errors = await self.agent_executor(
                    group_index,
                    action,
                )
                self.errors.extend(errors)
                if decision is ExecuteDecisionEnum.REJECTED:
                    return decision
        return type(self).result


class FakeSubAgentRuntime:
    instances: list["FakeSubAgentRuntime"] = []
    result = SubAgentResult(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[],
        turns_completed=3,
    )

    def __init__(
        self,
        *,
        session,
        model,
        memory,
        mcp_url: str,
        timeout_seconds: float,
        max_turns: int,
    ) -> None:
        self.session = session
        self.model = model
        self.memory = memory
        self.mcp_url = mcp_url
        self.timeout_seconds = timeout_seconds
        self.max_turns = max_turns
        type(self).instances.append(self)

    async def run_agent(self) -> SubAgentResult:
        return type(self).result


@pytest.fixture(autouse=True)
def fake_execution_process(monkeypatch) -> None:
    FakeExecutionProcess.instances = []
    FakeExecutionProcess.result = ExecuteDecisionEnum.ACCEPTED
    FakeExecutionProcess.errors = []
    FakeExecutionProcess.failure = None
    FakeSubAgentRuntime.instances = []
    FakeSubAgentRuntime.result = SubAgentResult(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[],
        turns_completed=3,
    )
    monkeypatch.setattr(
        execution_runtime,
        "ExecutionProcess",
        FakeExecutionProcess,
    )
    monkeypatch.setattr(
        execution_runtime,
        "SubAgentRuntime",
        FakeSubAgentRuntime,
    )


def runtime_memory() -> Memory:
    memory = Memory(goal="Test the motor")
    memory.tasks.append(current_task())
    return memory


def test_execution_runtime_runs_one_task_and_requests_review() -> None:
    memory = runtime_memory()
    expected_task = memory.get_current_task().task
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert result.requested_next_state is LoopStateEnum.REVIEW
    assert len(FakeExecutionProcess.instances) == 1
    assert FakeExecutionProcess.instances[0].actions_list == [
        expected_task
    ]
    assert result.event.event_type is EventTypeEnum.EXECUTION_RESULT
    assert result.event.payload["decision"] == "accepted"
    assert result.event.payload["step_goal"] == (
        "Set the motor speed to 10"
    )
    assert result.errors == []
    assert runtime.errors == []


def test_execution_runtime_records_failure_and_requests_review() -> None:
    FakeExecutionProcess.result = ExecuteDecisionEnum.REJECTED
    FakeExecutionProcess.errors = [
        ExecuteErrorSchema(
            event_name="Set the motor speed to 10",
            event_type=ExecutionTypeEnum.DISCRETE,
            position=0,
            error="motor rejected command",
        )
    ]
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert result.requested_next_state is LoopStateEnum.REVIEW
    assert result.event.payload["decision"] == "rejected"
    assert result.event.payload["errors"] == ["motor rejected command"]
    assert memory.event_ledger == [result.event]
    assert result.errors[0].error == "motor rejected command"
    assert runtime.errors[0].error == "motor rejected command"


def test_execution_runtime_rejects_incomplete_deterministic_actions() -> None:
    FakeExecutionProcess.result = ExecuteDecisionEnum.REJECTED
    FakeExecutionProcess.errors = [
        ExecuteErrorSchema(
            event_name="deterministic_actions",
            event_type=ExecutionTypeEnum.DISCRETE,
            position=0,
            error="Not all deterministic actions completed",
        )
    ]
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert result.event.payload["errors"] == [
        "Not all deterministic actions completed"
    ]
    assert runtime.errors[0].error == (
        "Not all deterministic actions completed"
    )


def test_execution_runtime_captures_process_exceptions() -> None:
    FakeExecutionProcess.failure = RuntimeError("invalid execution wiring")
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert runtime.errors[0].error == "invalid execution wiring"
    assert result.errors[0].error == "invalid execution wiring"
    assert result.event.payload["errors"] == ["invalid execution wiring"]


def test_execution_result_only_contains_errors_from_current_run() -> None:
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
        errors=[
            ExecuteErrorSchema(
                event_name="previous task",
                event_type=ExecutionTypeEnum.DISCRETE,
                position=0,
                error="previous error",
            )
        ],
    )

    result = asyncio.run(runtime.run_execution())

    assert result.errors == []
    assert [error.error for error in runtime.errors] == [
        "previous error"
    ]


def test_execution_runtime_dispatches_agent_action_to_subagent() -> None:
    memory = Memory(goal="Test adaptive movement")
    memory.tasks.append(current_agent_task())
    model = object()
    runtime = ExecutionRuntime(
        model=model,
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert result.errors == []
    assert result.event.payload["decision"] == "accepted"
    assert len(FakeSubAgentRuntime.instances) == 1
    subagent = FakeSubAgentRuntime.instances[0]
    assert subagent.model is model
    assert subagent.memory is memory
    assert subagent.mcp_url == "https://hardware.example.com/mcp"
    assert subagent.max_turns == 7
    assert subagent.timeout_seconds == 12.5
    assert len(FakeExecutionProcess.instances) == 1
    assert memory.get_current_task() is None


def test_execution_runtime_records_failed_subagent_result() -> None:
    error = ExecuteErrorSchema(
        event_name="observe",
        event_type=ExecutionTypeEnum.AGENT,
        position=2,
        error="Target is occluded",
    )
    FakeSubAgentRuntime.result = SubAgentResult(
        decision=ExecuteDecisionEnum.REJECTED,
        errors=[error],
        turns_completed=2,
    )
    memory = Memory(goal="Test adaptive movement")
    memory.tasks.append(current_agent_task())
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert result.errors == [error]
    assert runtime.errors == [error]
    assert result.event.payload["errors"] == ["Target is occluded"]
    assert memory.get_current_task() is None


def test_execution_runtime_runs_all_initialisation_tasks_before_review() -> None:
    first = current_task().task
    second = current_task().task.model_copy(
        update={"goal": "Set the motor speed to 20"}
    )
    memory = Memory(goal="Run the complete motor workflow")
    memory.current_hypothesis = SimpleNamespace(
        method=SimpleNamespace(execute_steps=[first, second])
    )
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert result.requested_next_state is LoopStateEnum.REVIEW
    assert len(FakeExecutionProcess.instances) == 1
    assert FakeExecutionProcess.instances[0].actions_list == [first, second]
    assert [task.status for task in memory.tasks] == [
        "completed",
        "completed",
    ]

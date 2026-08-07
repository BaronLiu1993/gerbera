import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionEventSchema,
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


@pytest.mark.parametrize(
    "schema, values",
    [
        (
            ExecutionEventSchema,
            {
                "event_name": "set_motor",
                "event_description": "Set motor speed",
                "event_type": ExecutionTypeEnum.DISCRETE,
                "status": ExecuteDecisionEnum.ACCEPTED,
                "position": -1,
                "error_msg": None,
            },
        ),
        (
            ExecuteErrorSchema,
            {
                "event_name": "set_motor",
                "event_type": ExecutionTypeEnum.DISCRETE,
                "position": -1,
                "error": "failed",
            },
        ),
    ],
)
def test_execution_positions_must_be_non_negative(schema, values) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(values)


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


def agent_memory() -> Memory:
    memory = Memory(goal="Test adaptive movement")
    task = current_agent_task()
    memory.tasks.append(task)
    memory.current_hypothesis = SimpleNamespace(
        method=SimpleNamespace(execute_steps=[task.task]),
        model_dump=lambda **kwargs: {"goal": "Test adaptive movement"},
    )
    return memory


class FakeExecutionProcess:
    instances: list["FakeExecutionProcess"] = []
    result = ExecuteDecisionEnum.ACCEPTED
    recorded_tool_events: list[dict[str, object]] = []
    failure: Exception | None = None

    def __init__(
        self,
        mcp_url: str,
        actions_list: list,
        agent_executor=None,
        on_group_started=None,
        on_group_completed=None,
    ) -> None:
        self.mcp_url = mcp_url
        self.actions_list = actions_list
        self.agent_executor = agent_executor
        self.on_group_started = on_group_started
        self.on_group_completed = on_group_completed
        self.tool_events = [
            dict(event) for event in type(self).recorded_tool_events
        ]
        type(self).instances.append(self)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        if type(self).failure is not None:
            raise type(self).failure
        for group_index, group in enumerate(self.actions_list):
            self.on_group_started(group_index, group)
            action = group.actions[0]
            if action.execution_type == "agent":
                decision = await self.agent_executor(
                    group_index,
                    action,
                )
                if decision is ExecuteDecisionEnum.REJECTED:
                    return decision
            if type(self).result is ExecuteDecisionEnum.ACCEPTED:
                self.on_group_completed(group_index, group)
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
        context,
        mcp_url: str,
        timeout_seconds: float,
        max_turns: int,
    ) -> None:
        self.session = session
        self.model = model
        self.context = context
        self.mcp_url = mcp_url
        self.timeout_seconds = timeout_seconds
        self.max_turns = max_turns
        self.observations = []
        self.tool_events = []
        type(self).instances.append(self)

    async def run_agent(self) -> SubAgentResult:
        return type(self).result


@pytest.fixture(autouse=True)
def fake_execution_process(monkeypatch) -> None:
    FakeExecutionProcess.instances = []
    FakeExecutionProcess.result = ExecuteDecisionEnum.ACCEPTED
    FakeExecutionProcess.recorded_tool_events = []
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
    task = current_task()
    memory.tasks.append(task)
    memory.current_hypothesis = SimpleNamespace(
        method=SimpleNamespace(execute_steps=[task.task])
    )
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


def test_execution_runtime_commits_deterministic_tool_evidence() -> None:
    FakeExecutionProcess.recorded_tool_events = [
        {
            "position": 0,
            "tool_name": "set_motor",
            "arguments": {"speed": 10},
            "status": "success",
            "result": {"speed": 10},
        }
    ]
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    asyncio.run(runtime.run_execution())

    tool_events = [
        event
        for event in memory.event_ledger
        if event.event_type is EventTypeEnum.TOOL_CALL
    ]
    assert tool_events[0].payload["arguments"] == {"speed": 10}
    assert tool_events[0].payload["result"] == {"speed": 10}


def test_execution_runtime_records_failure_and_requests_review() -> None:
    FakeExecutionProcess.result = ExecuteDecisionEnum.REJECTED
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
    assert result.event.payload["errors"] == []
    assert [event.event_type for event in memory.event_ledger] == [
        EventTypeEnum.TASK_STATUS_CHANGED,
        EventTypeEnum.EXECUTION_RESULT,
    ]
    assert memory.tasks[0].status == "failed"


def test_execution_runtime_rejects_incomplete_deterministic_actions() -> None:
    FakeExecutionProcess.result = ExecuteDecisionEnum.REJECTED
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert result.event.payload["errors"] == []


def test_execution_runtime_propagates_process_exceptions() -> None:
    FakeExecutionProcess.failure = RuntimeError("invalid execution wiring")
    memory = runtime_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    with pytest.raises(RuntimeError, match="invalid execution wiring"):
        asyncio.run(runtime.run_execution())

    assert memory.tasks[0].status == "in_progress"
    assert memory.event_ledger == []


def test_execution_runtime_fails_before_mutating_missing_task() -> None:
    memory = runtime_memory()
    memory.tasks.clear()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    with pytest.raises(IndexError):
        asyncio.run(runtime.run_execution())

    assert memory.tasks == []
    assert memory.event_ledger == []


def test_execution_runtime_dispatches_agent_action_to_subagent() -> None:
    memory = agent_memory()
    model = object()
    runtime = ExecutionRuntime(
        model=model,
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert result.event.payload["decision"] == "accepted"
    assert len(FakeSubAgentRuntime.instances) == 1
    subagent = FakeSubAgentRuntime.instances[0]
    assert subagent.model is model
    assert subagent.context.goal == memory.goal
    assert subagent.context.current_task == memory.tasks[0].task
    assert subagent.context.workflow_position == 0
    assert subagent.mcp_url == "https://hardware.example.com/mcp"
    assert subagent.max_turns == 7
    assert subagent.timeout_seconds == 12.5
    assert len(FakeExecutionProcess.instances) == 1
    assert memory.get_current_task() is None


def test_execution_runtime_commits_subagent_result_evidence() -> None:
    FakeSubAgentRuntime.result = SubAgentResult(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[],
        turns_completed=2,
        tool_events=[
            {
                "tool_name": "set_motor",
                "arguments": {"speed": 10},
                "status": "success",
                "result": {"speed": 10},
            }
        ],
    )
    memory = agent_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    tool_events = [
        event
        for event in memory.event_ledger
        if event.event_type is EventTypeEnum.TOOL_CALL
    ]
    assert tool_events[0].payload["arguments"] == {"speed": 10}


def test_execution_runtime_drops_errors_from_accepted_subagent() -> None:
    recovered_error = ExecuteErrorSchema(
        event_name="set_motor",
        event_type=ExecutionTypeEnum.AGENT,
        position=3,
        error="Recovered motor failure",
    )
    FakeSubAgentRuntime.result = SimpleNamespace(
        decision=ExecuteDecisionEnum.ACCEPTED,
        errors=[recovered_error],
        turns_completed=4,
        observations=[],
        tool_events=[],
    )
    memory = agent_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.ACCEPTED
    assert memory.completed_tasks == memory.tasks


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
    memory = agent_memory()
    runtime = ExecutionRuntime(
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    result = asyncio.run(runtime.run_execution())

    assert result.decision is ExecuteDecisionEnum.REJECTED
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
    memory.initialize_tasks(memory.current_hypothesis)
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
    assert memory.completed_tasks == memory.tasks

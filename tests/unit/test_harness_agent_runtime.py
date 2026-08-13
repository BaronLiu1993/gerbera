import asyncio
from types import SimpleNamespace

from gerbera_harness.domain.session import (
    Execution,
    ExecuteDecisionEnum,
    InitialisationDecisionEnum,
    LoopStateEnum,
    Review,
    ReviewDecisionEnum,
    Session,
)
from gerbera_harness.workflows import agent_runtime as agent_runtime
from gerbera_harness.workflows.agent_runtime import AgentRuntime
from gerbera_harness.memory import Memory
from gerbera_harness.memory import TaskSchema
from gerbera_harness.tools.registry import LocalToolRegistry


def execution_group():
    return TaskSchema.model_validate(
        {
            "status": "pending",
            "task": {
                "goal": "Set the motor speed",
                "action_type": "execute",
                "actions": [
                    {
                        "description": "Set motor speed",
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
    ).task


def test_agent_runtime_moves_accepted_execution_to_review(
    monkeypatch,
) -> None:
    model = object()

    class FakeExecutionRuntime:
        def __init__(self, model, memory: Memory, mcp_url: str) -> None:
            self.model = model
            self.memory = memory
            self.mcp_url = mcp_url

        async def run_execution(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ExecuteDecisionEnum.ACCEPTED,
                requested_next_state=LoopStateEnum.REVIEW,
            )

    class FakeReviewRuntime:
        def __init__(self, model, memory: Memory, context_builder) -> None:
            self.model = model
            self.memory = memory
            self.context_builder = context_builder

        async def run_review(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ReviewDecisionEnum.ACCEPTED,
            )

    monkeypatch.setattr(
        agent_runtime,
        "ExecutionRuntime",
        FakeExecutionRuntime,
    )
    monkeypatch.setattr(
        agent_runtime,
        "ReviewRuntime",
        FakeReviewRuntime,
    )
    runtime = AgentRuntime(
        session=Session(state=Execution()),
        model=model,
        memory=Memory(goal="Move the motor"),
        mcp_url="https://hardware.example.com/mcp",
        local_tool_registry=LocalToolRegistry(),
        feedback=[],
    )

    asyncio.run(runtime.run_agent("unused during execution"))

    assert runtime.execution_runtime.model is model
    assert isinstance(runtime.session.state, Review)


def test_agent_runtime_stops_after_rejected_execution(monkeypatch) -> None:
    review_called = False

    class FakeExecutionRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        async def run_execution(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ExecuteDecisionEnum.REJECTED,
                requested_next_state=LoopStateEnum.REVIEW,
            )

    class FakeReviewRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        async def run_review(self) -> SimpleNamespace:
            nonlocal review_called
            review_called = True
            return SimpleNamespace(decision=ReviewDecisionEnum.ACCEPTED)

    monkeypatch.setattr(
        agent_runtime,
        "ExecutionRuntime",
        FakeExecutionRuntime,
    )
    monkeypatch.setattr(
        agent_runtime,
        "ReviewRuntime",
        FakeReviewRuntime,
    )
    runtime = AgentRuntime(
        session=Session(state=Execution()),
        model=object(),
        memory=Memory(goal="Move the motor"),
        mcp_url="https://hardware.example.com/mcp",
        local_tool_registry=LocalToolRegistry(),
        feedback=[],
    )

    result = asyncio.run(runtime.run_agent("Move the motor"))

    assert result is None
    assert isinstance(runtime.session.state, Execution)
    assert review_called is False


def test_agent_runtime_pauses_replan_in_review(monkeypatch) -> None:
    feedback = ["Collect another measurement"]

    class FakeReviewRuntime:
        def __init__(self, model, memory: Memory, context_builder) -> None:
            pass

        async def run_review(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ReviewDecisionEnum.REPLAN,
                feedback=feedback,
                requested_next_state=LoopStateEnum.INITIALISATION,
            )

    monkeypatch.setattr(
        agent_runtime,
        "ReviewRuntime",
        FakeReviewRuntime,
    )
    runtime = AgentRuntime(
        session=Session(state=Review()),
        model=object(),
        memory=Memory(goal="Move the motor"),
        mcp_url="https://hardware.example.com/mcp",
        local_tool_registry=LocalToolRegistry(),
        feedback=[],
    )

    asyncio.run(runtime.run_agent("unused during review"))

    assert runtime.feedback == feedback
    assert isinstance(runtime.session.state, Review)


def test_accepted_initialisation_creates_pending_tasks(monkeypatch) -> None:
    group = execution_group()
    hypothesis = SimpleNamespace(
        method=SimpleNamespace(execute_steps=[group])
    )

    class FakeInitialisationRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        async def run_initial(self, prompt, feedback) -> SimpleNamespace:
            return SimpleNamespace(
                decision=InitialisationDecisionEnum.ACCEPTED,
                hypothesis=hypothesis,
                requested_next_state=LoopStateEnum.EXECUTION,
            )

    class FakeExecutionRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        async def run_execution(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ExecuteDecisionEnum.ACCEPTED,
                requested_next_state=LoopStateEnum.REVIEW,
            )

    class FakeReviewRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        async def run_review(self) -> SimpleNamespace:
            return SimpleNamespace(decision=ReviewDecisionEnum.ACCEPTED)

    monkeypatch.setattr(
        agent_runtime,
        "InitialisationRuntime",
        FakeInitialisationRuntime,
    )
    monkeypatch.setattr(
        agent_runtime,
        "ExecutionRuntime",
        FakeExecutionRuntime,
    )
    monkeypatch.setattr(
        agent_runtime,
        "ReviewRuntime",
        FakeReviewRuntime,
    )
    memory = Memory(goal="Move the motor")
    runtime = AgentRuntime(
        session=Session(),
        model=object(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
        local_tool_registry=LocalToolRegistry(),
        feedback=[],
    )

    asyncio.run(runtime.run_agent("Move the motor"))

    assert runtime.memory is not memory
    assert runtime.memory.session_id == memory.session_id
    assert runtime.memory.current_hypothesis is hypothesis
    assert [task.task for task in runtime.memory.tasks] == [group]
    assert [task.status for task in runtime.memory.tasks] == ["pending"]
    assert runtime.memory.completed_tasks == []

import asyncio
from types import SimpleNamespace

from gerbera_harness.agent.driver.main_loop import (
    Execution,
    ExecuteDecisionEnum,
    InitialisationDecisionEnum,
    LoopStateEnum,
    Review,
    ReviewDecisionEnum,
    Session,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent_runtime import agent_runtime
from gerbera_harness.agent_runtime.agent_runtime import AgentRuntime
from gerbera_harness.memory import Memory
from gerbera_harness.memory import TaskSchema


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


def test_agent_runtime_collects_execution_errors_and_moves_to_review(
    monkeypatch,
) -> None:
    execution_errors = [
        ExecuteErrorSchema(
            event_name="move_motor",
            event_type=ExecutionTypeEnum.DISCRETE,
            position=0,
            error="motor rejected command",
        )
    ]
    model = object()

    class FakeExecutionRuntime:
        def __init__(self, model, memory: Memory, mcp_url: str) -> None:
            self.model = model
            self.memory = memory
            self.mcp_url = mcp_url

        async def run_execution(self) -> SimpleNamespace:
            return SimpleNamespace(
                decision=ExecuteDecisionEnum.ACCEPTED,
                errors=execution_errors,
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
        feedback=[],
    )

    asyncio.run(runtime.run_agent("unused during execution"))

    assert runtime.errors == execution_errors
    assert runtime.errors is not execution_errors
    assert runtime.execution_runtime.model is model
    assert isinstance(runtime.session.state, Review)


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
                errors=[],
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
        feedback=[],
    )

    asyncio.run(runtime.run_agent("Move the motor"))

    assert memory.current_hypothesis is hypothesis
    assert [task.task for task in memory.tasks] == [group]
    assert [task.status for task in memory.tasks] == ["pending"]
    assert memory.completed_tasks == []

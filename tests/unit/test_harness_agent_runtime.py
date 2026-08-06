import asyncio
from types import SimpleNamespace

from gerbera_harness.agent.driver.main_loop import (
    Execution,
    ExecuteDecisionEnum,
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

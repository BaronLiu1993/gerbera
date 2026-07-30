import pytest
from pydantic import ValidationError

from gerbera_harness.agent.driver.subloop import (
    ActState,
    DecideResultSchema,
    DecideState,
    ExecuteLoop,
    ExecuteLoopDecisionEnum,
    ExecuteLoopStateEnum,
    ObserveState,
)


def test_continue_decision_advances_to_act_and_observe() -> None:
    loop = ExecuteLoop()

    assert isinstance(loop.state, ObserveState)
    assert isinstance(
        loop.perform_transition(ExecuteLoopStateEnum.DECIDE),
        DecideState,
    )
    assert loop.resolve_decision("continue") is ExecuteLoopDecisionEnum.CONTINUE
    assert isinstance(loop.state, ActState)
    assert isinstance(loop.perform_transition("observe"), ObserveState)
    assert loop.decision is None


@pytest.mark.parametrize("decision", ["complete", "incomplete"])
def test_terminal_decision_stops_execute_loop(decision: str) -> None:
    loop = ExecuteLoop(state=DecideState())

    loop.resolve_decision(decision)

    assert loop.terminated is True
    assert loop.valid_transition(ExecuteLoopStateEnum.ACT) is False
    with pytest.raises(ValueError, match="Invalid execute-loop transition"):
        loop.perform_transition(ExecuteLoopStateEnum.ACT)


def test_decision_can_only_be_resolved_in_decide_state() -> None:
    loop = ExecuteLoop()

    with pytest.raises(ValueError, match="only be resolved in decide state"):
        loop.resolve_decision("continue")


@pytest.mark.parametrize("decision", ["complete", "incomplete", "continue"])
def test_decide_result_schema_accepts_loop_decisions(decision: str) -> None:
    result = DecideResultSchema.model_validate({"decision": decision})

    assert result.decision.value == decision


def test_decide_result_schema_rejects_unknown_decision() -> None:
    with pytest.raises(ValidationError):
        DecideResultSchema.model_validate({"decision": "retry"})

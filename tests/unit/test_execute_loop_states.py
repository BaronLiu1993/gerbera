import pytest

from gerbera_harness.agent.experiments.states.schema.execute import (
    ActState,
    CompletedState,
    DecideState,
    ExecuteLoop,
    ExecuteLoopStateEnum,
    IncompleteState,
    ObserveState,
)


def test_execute_loop_continues_when_observation_is_incomplete() -> None:
    loop = ExecuteLoop()

    assert isinstance(loop.state, ObserveState)
    assert isinstance(
        loop.perform_transition(ExecuteLoopStateEnum.INCOMPLETE),
        IncompleteState,
    )
    assert isinstance(
        loop.perform_transition(ExecuteLoopStateEnum.DECIDE),
        DecideState,
    )
    assert isinstance(loop.perform_transition("act"), ActState)
    assert isinstance(loop.perform_transition("observe"), ObserveState)


def test_execute_loop_finishes_when_observation_is_completed() -> None:
    loop = ExecuteLoop()

    assert isinstance(loop.perform_transition("completed"), CompletedState)
    assert loop.state.valid_transition_states == frozenset()


@pytest.mark.parametrize(
    ("state", "invalid_target"),
    [
        (ObserveState(), ExecuteLoopStateEnum.ACT),
        (IncompleteState(), ExecuteLoopStateEnum.ACT),
        (DecideState(), ExecuteLoopStateEnum.OBSERVE),
        (ActState(), ExecuteLoopStateEnum.DECIDE),
        (CompletedState(), ExecuteLoopStateEnum.OBSERVE),
    ],
)
def test_execute_loop_rejects_out_of_order_transitions(
    state: (
        ObserveState
        | IncompleteState
        | DecideState
        | ActState
        | CompletedState
    ),
    invalid_target: ExecuteLoopStateEnum,
) -> None:
    loop = ExecuteLoop(state=state)

    with pytest.raises(ValueError, match="Invalid execute-loop transition"):
        loop.perform_transition(invalid_target)

    assert loop.state is state

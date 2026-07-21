from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import (
    Execute,
    LoopStateEnum,
    Observe,
    Plan,
    Review,
)


def test_experiment_states_only_allow_the_next_cycle_phase() -> None:
    session = Session()

    assert isinstance(session.state, Plan)
    assert session.phase is LoopStateEnum.PLAN
    assert session.valid_transition(LoopStateEnum.EXECUTE) is True
    assert session.valid_transition(LoopStateEnum.OBSERVE) is False

    assert Execute().valid_transition(LoopStateEnum.OBSERVE) is True
    assert Execute().valid_transition(LoopStateEnum.REVIEW) is False
    assert Observe().valid_transition(LoopStateEnum.REVIEW) is True
    assert Observe().valid_transition(LoopStateEnum.PLAN) is False
    assert Review().valid_transition(LoopStateEnum.PLAN) is True
    assert Review().valid_transition(LoopStateEnum.EXECUTE) is False

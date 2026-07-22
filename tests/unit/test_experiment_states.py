import pytest

from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execution,
    Failed,
    Initialisation,
    Observation,
    Review,
)
from gerbera_sdk.harness.agent.experiments.states.base import (
    DecisionEnum,
)


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [
        Initialisation(),
        Execution(),
        Observation(),
        Review(),
        Complete(),
        Failed(),
    ]

    for state in states:
        assert state.prompt_path.name == state.system_prompt
        assert state.prompt_path.suffix == ".md"
        assert state.prompt.startswith(f"# {state.state.value.title()}")


def test_experiment_cycle_enforces_valid_transitions() -> None:
    assert Initialisation().valid_transition(Initialisation.state)
    assert Initialisation().valid_transition(Execution.state)
    assert Execution().valid_transition(Observation.state)
    assert Observation().valid_transition(Review.state)
    assert Review().valid_transition(Execution.state)
    assert Review().valid_transition(Complete.state)
    assert Review().valid_transition(Failed.state)
    assert not Review().valid_transition(Initialisation.state)
    assert Complete.terminal
    assert Failed.terminal


def test_initialisation_accepts_only_readiness_decisions() -> None:
    assert Initialisation.valid_decisions == frozenset(
        {DecisionEnum.ACCEPTED, DecisionEnum.REJECTED}
    )


def test_state_owns_transition_validation_and_creation() -> None:
    assert isinstance(Initialisation().transition(Execution.state), Execution)

    with pytest.raises(ValueError, match="initialisation to observation"):
        Initialisation().transition(Observation.state)


def test_state_output_schema_uses_only_valid_transition_values() -> None:
    states = [Execution(), Observation(), Review()]

    for state in states:
        assert "valid_schema" in type(state).__dict__
        assert set(state.valid_schema["properties"]) == {
            "next_state",
            "response",
        }
        assert state.valid_schema["properties"]["response"] == {
            "type": "string"
        }
        assert state.valid_schema["properties"]["next_state"]["enum"] == sorted(
            transition.value for transition in state.valid_transition_states
        )

    assert Initialisation.valid_schema["properties"]["next_state"] == {
        "enum": ["execution", "initialisation"],
        "type": "string",
    }
    assert Initialisation.valid_schema["properties"]["response"]["type"] == (
        "object"
    )

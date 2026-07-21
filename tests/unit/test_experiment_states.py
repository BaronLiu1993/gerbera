from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execution,
    Failed,
    Initialisation,
    Observation,
    Plan,
    Review,
)
from gerbera_sdk.harness.agent.agent import TERMINAL_STATES


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [
        Initialisation(),
        Plan(),
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
    assert Initialisation().valid_transition(Plan.state)
    assert Plan().valid_transition(Execution.state)
    assert Execution().valid_transition(Observation.state)
    assert Observation().valid_transition(Review.state)
    assert Review().valid_transition(Plan.state)
    assert Review().valid_transition(Complete.state)
    assert Review().valid_transition(Failed.state)
    assert not Review().valid_transition(Initialisation.state)
    assert not Review().valid_transition(Execution.state)
    assert Complete.state in TERMINAL_STATES
    assert Failed.state in TERMINAL_STATES


def test_state_output_schema_uses_only_valid_transition_values() -> None:
    states = [
        Initialisation(),
        Plan(),
        Execution(),
        Observation(),
        Review(),
    ]

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

from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execute,
    Hypothesize,
    Observe,
    Plan,
    Review,
)


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [Hypothesize(), Plan(), Execute(), Observe(), Review(), Complete()]

    for state in states:
        assert state.prompt_path.name == state.system_prompt
        assert state.prompt_path.suffix == ".md"
        assert state.prompt.startswith(f"# {state.state.value.title()}")


def test_experiment_cycle_allows_rehypothesizing_after_review() -> None:
    assert Hypothesize().valid_transition(Plan.state)
    assert Review().valid_transition(Hypothesize.state)
    assert Review().valid_transition(Plan.state)
    assert Review().valid_transition(Complete.state)


def test_state_output_schema_uses_only_valid_transition_values() -> None:
    states = [Hypothesize(), Plan(), Execute(), Observe(), Review(), Complete()]

    for state in states:
        assert "valid_schema" in type(state).__dict__
        assert state.valid_schema["properties"]["next_state"]["enum"] == sorted(
            transition.value for transition in state.valid_transition_states
        )

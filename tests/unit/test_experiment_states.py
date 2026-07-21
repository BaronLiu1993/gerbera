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
        assert state.prompt.startswith(f"# {state.phase.value.title()}")


def test_experiment_cycle_allows_rehypothesizing_after_review() -> None:
    assert Hypothesize().valid_transition(Plan.phase)
    assert Review().valid_transition(Hypothesize.phase)
    assert Review().valid_transition(Plan.phase)
    assert Review().valid_transition(Complete.phase)

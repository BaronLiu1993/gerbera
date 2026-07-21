from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execute,
    Observe,
    Plan,
    Review,
)


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [Plan(), Execute(), Observe(), Review(), Complete()]

    for state in states:
        assert state.prompt_path.name == state.system_prompt
        assert state.prompt_path.suffix == ".md"
        assert state.prompt.startswith(f"# {state.phase.value.title()}")

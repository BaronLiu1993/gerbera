import pytest

from gerbera_sdk.harness.agent.experiments.states import (
    Complete,
    Execution,
    Failed,
    Initialisation,
    Review,
)
from gerbera_sdk.harness.agent.experiments.states.base import (
    DecisionEnum,
)
from gerbera_sdk.harness.agent.experiments.session import Session


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [
        Initialisation(),
        Execution(),
        Review(),
        Complete(),
        Failed(),
    ]

    for state in states:
        assert state.prompt_path.name == state.prompt_file
        assert state.system_prompt.startswith("#")
        assert state.prompt_path.suffix == ".md"
        assert state.prompt.startswith(f"# {state.state.value.title()}")


def test_experiment_cycle_enforces_valid_transitions() -> None:
    assert Initialisation().valid_transition(Initialisation.state)
    assert Initialisation().valid_transition(Execution.state)
    assert Execution().valid_transition(Execution.state)
    assert Execution().valid_transition(Review.state)
    assert Review().valid_transition(Execution.state)
    assert Review().valid_transition(Complete.state)
    assert Review().valid_transition(Failed.state)
    assert not Review().valid_transition(Initialisation.state)


def test_session_replaces_state_during_transition() -> None:
    session = Session()
    initial_state = session.state

    new_state = session.perform_transition(Execution.state)

    assert isinstance(new_state, Execution)
    assert session.state is new_state
    assert session.state is not initial_state


def test_session_rejects_invalid_transition() -> None:
    session = Session()
    initial_state = session.state

    with pytest.raises(
        ValueError,
        match="initialisation -> review",
    ):
        session.perform_transition(Review.state)

    assert session.state is initial_state


def test_initialisation_accepts_only_readiness_decisions() -> None:
    assert Initialisation.valid_decisions == frozenset(
        {DecisionEnum.ACCEPTED, DecisionEnum.REJECTED}
    )


def test_initialisation_output_schema_uses_valid_transitions() -> None:
    assert Initialisation.valid_schema["properties"]["next_state"] == {
        "enum": ["execution", "initialisation"],
        "type": "string",
    }
    response_options = Initialisation.valid_schema["properties"]["response"][
        "anyOf"
    ]
    assert response_options[0]["type"] == "object"
    assert response_options[1] == {"type": "null"}
    assert Initialisation.valid_schema["properties"]["decision"] == {
        "type": "string",
        "enum": ["accepted", "rejected"],
    }


def test_initialisation_prompt_requires_continuous_time_series() -> None:
    prompt = Initialisation().system_prompt

    assert "You MUST use `continuous`" in prompt
    assert "repeated timestamped readings" in prompt
    assert "IR sensor output remains stable over 30 seconds" in prompt
    assert "Do not represent a time-series experiment" in prompt


def test_initialisation_prompt_requires_parameter_lists() -> None:
    prompt = Initialisation().system_prompt

    assert "Parameter-list fields are mandatory" in prompt
    assert "Every `discrete` action must include `params`" in prompt
    assert "both `forward_tool_call_params` and" in prompt
    assert "`reverse_tool_call_params`" in prompt
    assert "Never omit a parameter-list field" in prompt

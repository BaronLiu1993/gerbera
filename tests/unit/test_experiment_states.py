import pytest
from pydantic import ValidationError

from gerbera_harness.agent.driver.main_loop import (
    Execution,
    Initialisation,
    InitialisationDecisionEnum,
    LoopStateEnum,
    Session,
    Review,
)
from gerbera_harness.agent.driver.main_loop.schema.initialisation import (
    InitialisationResponseSchema,
)


def test_each_experiment_state_loads_its_markdown_prompt() -> None:
    states = [
        Initialisation(),
        Execution(),
        Review(),
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
    assert Review().valid_transition(Initialisation.state)
    assert not Review().valid_transition(Execution.state)
    assert not Review().valid_transition(Review.state)


def test_session_replaces_state_during_transition() -> None:
    session = Session()
    initial_state = session.state

    new_state = session.perform_transition(Execution.state)

    assert isinstance(new_state, Execution)
    assert session.state is new_state
    assert session.state is not initial_state


def test_main_loop_sessions_have_independent_run_ids() -> None:
    first = Session()
    second = Session()

    assert first.run_id
    assert second.run_id
    assert first.run_id != second.run_id


def test_session_rejects_invalid_transition() -> None:
    session = Session()
    initial_state = session.state

    with pytest.raises(
        ValueError,
        match="initialisation -> review",
    ):
        session.perform_transition(Review.state)

    assert session.state is initial_state


def test_states_do_not_own_model_output_schemas() -> None:
    for state_type in (Initialisation, Execution, Review):
        assert not hasattr(state_type, "valid_schema")
        assert not hasattr(state_type, "valid_decisions")


def test_initialisation_response_owns_transition_validation() -> None:
    response = InitialisationResponseSchema(
        decision=InitialisationDecisionEnum.ACCEPTED,
        next_state=LoopStateEnum.EXECUTION,
        issues=[],
        rejection_reasons=[],
        clarifying_questions=[],
    )

    assert response.next_state is LoopStateEnum.EXECUTION

    with pytest.raises(ValidationError):
        InitialisationResponseSchema(
            decision=InitialisationDecisionEnum.ACCEPTED,
            next_state=LoopStateEnum.INITIALISATION,
            issues=[],
            rejection_reasons=[],
            clarifying_questions=[],
        )


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

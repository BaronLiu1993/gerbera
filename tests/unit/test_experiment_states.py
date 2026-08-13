import pytest
from pydantic import ValidationError

from gerbera_harness.domain.session import (
    Execution,
    Initialisation,
    InitialisationDecisionEnum,
    LoopStateEnum,
    Session,
    Review,
)
from gerbera_harness.domain.responses import (
    InitialisationResponseSchema,
)
from gerbera_harness.domain.experiment import (
    HypothesisSchema,
)


def test_experiment_states_do_not_own_prompts() -> None:
    states = [
        Initialisation(),
        Execution(),
        Review(),
    ]

    for state in states:
        assert not hasattr(state, "prompt_file")
        assert not hasattr(state, "prompt_path")
        assert not hasattr(state, "system_prompt")
        assert not hasattr(state, "prompt")


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


def test_main_loop_sessions_have_independent_session_ids() -> None:
    first = Session()
    second = Session()

    assert first.session_id
    assert second.session_id
    assert first.session_id != second.session_id


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
    hypothesis = HypothesisSchema.model_construct()
    response = InitialisationResponseSchema(
        response={
            "decision": InitialisationDecisionEnum.ACCEPTED,
            "next_state": LoopStateEnum.EXECUTION,
            "hypothesis": hypothesis,
            "issues": [],
            "rejection_reasons": [],
            "clarifying_questions": [],
        }
    )

    assert response.response.next_state is LoopStateEnum.EXECUTION

    with pytest.raises(ValidationError):
        InitialisationResponseSchema(
            response={
                "decision": InitialisationDecisionEnum.ACCEPTED,
                "next_state": LoopStateEnum.INITIALISATION,
                "hypothesis": hypothesis,
                "issues": [],
                "rejection_reasons": [],
                "clarifying_questions": [],
            }
        )

    with pytest.raises(ValidationError):
        InitialisationResponseSchema(
            response={
                "decision": InitialisationDecisionEnum.REJECTED,
                "next_state": LoopStateEnum.INITIALISATION,
                "hypothesis": None,
                "issues": ["More information is required."],
                "rejection_reasons": ["The workflow cannot proceed."],
                "clarifying_questions": [
                    {
                        "question": "How long should collection run?",
                        "options": ["10 seconds", "30 seconds"],
                    }
                ],
            }
        )

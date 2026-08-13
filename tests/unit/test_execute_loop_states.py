from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gerbera_harness.domain.adaptive import (
    ActState,
    DecideResultSchema,
    DecideState,
    ExecuteLoop,
    ExecuteLoopDecisionEnum,
    ExecuteLoopStateEnum,
    ObserveSchema,
    ObserveState,
)


def test_continue_decision_advances_to_act_and_observe() -> None:
    loop = ExecuteLoop()

    assert isinstance(loop.state, ObserveState)
    assert isinstance(
        loop.perform_transition(ExecuteLoopStateEnum.DECIDE),
        DecideState,
    )
    assert loop.resolve_decision("continue") is ExecuteLoopDecisionEnum.CONTINUE
    assert isinstance(loop.state, ActState)
    assert isinstance(loop.perform_transition("observe"), ObserveState)
    assert loop.decision is None


@pytest.mark.parametrize("decision", ["complete", "incomplete"])
def test_terminal_decision_stops_execute_loop(decision: str) -> None:
    loop = ExecuteLoop(state=DecideState())

    loop.resolve_decision(decision)

    assert loop.terminated is True
    assert loop.valid_transition(ExecuteLoopStateEnum.ACT) is False
    with pytest.raises(ValueError, match="Invalid execute-loop transition"):
        loop.perform_transition(ExecuteLoopStateEnum.ACT)


def test_decision_can_only_be_resolved_in_decide_state() -> None:
    loop = ExecuteLoop()

    with pytest.raises(ValueError, match="only be resolved in decide state"):
        loop.resolve_decision("continue")


@pytest.mark.parametrize("decision", ["complete", "incomplete", "continue"])
def test_decide_result_schema_accepts_loop_decisions(decision: str) -> None:
    result = DecideResultSchema.model_validate({"decision": decision})

    assert result.decision.value == decision


def test_decide_result_schema_rejects_unknown_decision() -> None:
    with pytest.raises(ValidationError):
        DecideResultSchema.model_validate({"decision": "retry"})


def test_observe_schema_collects_read_only_space_information() -> None:
    observed_at = datetime.now(timezone.utc)

    observation = ObserveSchema.model_validate(
        {
            "space_name": "workshop",
            "observed_from": observed_at,
            "observed_until": observed_at,
            "read_only": True,
            "observations": [
                {
                    "type": "sensor",
                    "event_id": "sensor-event",
                    "source_name": "distance_sensor",
                    "microcontroller_id": "board-1",
                    "event_name": "distance-stream",
                    "observed_at": observed_at,
                    "readings": [
                        {
                            "name": "distance",
                            "value": 12.5,
                            "unit": "cm",
                        }
                    ],
                    "stale": False,
                },
                {
                    "type": "camera",
                    "event_id": "camera-event",
                    "source_name": "local_camera",
                    "observed_at": observed_at,
                    "frame_id": "frame-1",
                    "vision": {
                        "environment_name": "workshop",
                        "description": "A workbench",
                        "objects": [],
                    },
                    "stale": False,
                },
            ],
            "complete": True,
            "errors": [],
        }
    )

    assert len(observation.observations) == 2
    assert observation.read_only is True


def test_observe_schema_rejects_actions_and_invalid_time_windows() -> None:
    observed_at = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        ObserveSchema.model_validate(
            {
                "space_name": "workshop",
                "observed_from": observed_at,
                "observed_until": observed_at,
                "read_only": True,
                "observations": [],
                "complete": True,
                "errors": [],
                "actions": ["turn_off_motor"],
            }
        )

    with pytest.raises(ValidationError, match="observed_from"):
        ObserveSchema.model_validate(
            {
                "space_name": "workshop",
                "observed_from": "2026-08-01T00:00:01Z",
                "observed_until": "2026-08-01T00:00:00Z",
                "read_only": True,
                "observations": [],
                "complete": True,
                "errors": [],
            }
        )

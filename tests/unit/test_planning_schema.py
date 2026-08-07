import pytest
from pydantic import ValidationError

from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningResponseSchema,
    PlanningReviewSchema,
    PlanningStatusEnum,
)


def action_parameter(
    tool_parameter: str,
    value: bool | int | float | str,
    parameter_type: str,
    unit: str | None = None,
) -> dict[str, object]:
    return {
        "tool_parameter": tool_parameter,
        "value": value,
        "unit": unit,
        "type": parameter_type,
    }


@pytest.mark.parametrize(
    ("action", "execution_type"),
    [
        (
            {
                "description": "Move the motor to 90 degrees.",
                "action_type": "execute",
                "execution_type": "discrete",
                "start_offset_seconds": 0,
                "dependent_variables": ["acknowledged_angle"],
                "independent_variables": ["commanded_angle"],
                "forward_tool_call": "write_motor",
                "params": [
                    action_parameter(
                        "angle",
                        90,
                        "int",
                        "degrees",
                    )
                ],
            },
            "discrete",
        ),
        (
            {
                "description": "Run the heater for 30 seconds.",
                "action_type": "execute",
                "execution_type": "continuous",
                "start_offset_seconds": 0,
                "duration_seconds": 30,
                "dependent_variables": ["temperature"],
                "independent_variables": ["heater_state"],
                "forward_tool_call": "start_heater",
                "reverse_tool_call": "stop_heater",
                "forward_tool_call_params": [
                    action_parameter("heater_state", True, "bool")
                ],
                "reverse_tool_call_params": [],
                "emitted_event_keys": [
                    {
                        "event_type": "STREAM",
                        "microcontroller_id": "board-1",
                        "event_name": "temperature",
                    }
                ],
            },
            "continuous",
        ),
    ],
)
def test_planning_response_accepts_one_execute_action(
    action: dict[str, object],
    execution_type: str,
) -> None:
    response = PlanningResponseSchema.model_validate({"action": action})

    assert response.action.execution_type == execution_type


def test_planning_response_rejects_agent_actions() -> None:
    with pytest.raises(ValidationError):
        PlanningResponseSchema.model_validate(
            {
                "action": {
                    "action_type": "execute",
                    "execution_type": "agent",
                    "goal": "Move within reach.",
                    "completion_criteria": "The block is within reach.",
                    "max_turns": 3,
                    "timeout_seconds": 30,
                }
            }
        )


def test_planning_response_rejects_execution_step_lists() -> None:
    with pytest.raises(ValidationError):
        PlanningResponseSchema.model_validate({"execution_steps": []})


@pytest.mark.parametrize("status", ["ready", "blocked", "continue"])
def test_planning_review_accepts_loop_statuses(status: str) -> None:
    review = PlanningReviewSchema.model_validate(
        {"status": status, "feedback": "details"}
    )

    assert review.status is PlanningStatusEnum(status)


def test_planning_review_rejects_boolean_approval() -> None:
    with pytest.raises(ValidationError):
        PlanningReviewSchema.model_validate(
            {"approved": True, "feedback": ""}
        )

import pytest
from pydantic import ValidationError

from gerbera_harness.domain.adaptive import (
    PlanningResponseSchema,
    PlanningReviewSchema,
    PlanningStatusEnum,
)
from gerbera_harness.domain.adaptive import (
    ObservationResponseSchema,
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


def test_model_output_schemas_use_supported_object_shapes() -> None:
    for schema in (
        PlanningResponseSchema.model_json_schema(),
        ObservationResponseSchema.model_json_schema(),
    ):
        assert_schema_uses_supported_object_shapes(schema)


def assert_schema_uses_supported_object_shapes(schema: dict) -> None:
    unsupported = {
        "oneOf",
        "allOf",
        "not",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
        "discriminator",
    }

    def visit(node: object) -> None:
        if isinstance(node, dict):
            assert not unsupported.intersection(node)
            if node.get("type") == "array":
                assert "items" in node
            if "properties" in node:
                assert set(node["properties"]) == set(node.get("required", []))
                assert node.get("additionalProperties") is False
            assert node != {}
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    assert schema.get("type") == "object"
    visit(schema)

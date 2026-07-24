import pytest
from pydantic import ValidationError

from gerbera_sdk.harness.agent.experiments.states.schema import (
    HypothesisSchema,
    ReviewSchema,
    StepSchema,
)


def action_parameter(
    variable: str,
    value: bool | int | float | str,
    parameter_type: str,
    unit: str | None = None,
) -> dict:
    return {
        "variable": variable,
        "value": value,
        "unit": unit,
        "type": parameter_type,
    }


def discrete_execute_action() -> dict:
    return {
        "action_type": "execute",
        "execution_type": "discrete",
        "dependent_variables": ["acknowledged_angle"],
        "independent_variables": ["commanded_angle"],
        "forward_tool_call": "write_motor",
        "params": [
            action_parameter(
                variable="commanded_angle",
                value=90,
                parameter_type="int",
                unit="degrees",
            )
        ],
    }


def continuous_execute_action() -> dict:
    return {
        "action_type": "execute",
        "execution_type": "continuous",
        "duration_seconds": 30,
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "forward_tool_call": "start_heater",
        "reverse_tool_call": "stop_heater",
        "forward_tool_call_params": [
            action_parameter(
                variable="heater_state",
                value=True,
                parameter_type="bool",
            )
        ],
        "reverse_tool_call_params": [],
    }


def review_action() -> dict:
    return {
        "action_type": "review",
        "analysis_goal": (
            "Compare average temperature with the heater on and off."
        ),
        "data_variables": ["temperature", "heater_state"],
        "review_tool_calls": [
            {
                "tool": "query_experiment_data",
                "params": [
                    action_parameter(
                        variable="query",
                        value=(
                            "SELECT heater_state, AVG(temperature) "
                            "FROM readings GROUP BY heater_state"
                        ),
                        parameter_type="string",
                    )
                ],
            }
        ],
        "expected": "Average temperature is higher when the heater is on.",
    }


def hypothesis_data(action: dict) -> dict:
    return {
        "hypothesis": "Heating increases measured temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "methods": [
            {
                "name": "heating_test",
                "description": "Compare temperature before and after heating.",
                "steps": [
                    {
                        "description": "Run the planned action.",
                        "action": action,
                    }
                ],
            }
        ],
    }


def test_hypothesis_schema_models_an_execute_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(discrete_execute_action())
    )

    action = hypothesis.methods[0].steps[0].action
    assert action.forward_tool_call == "write_motor"
    assert action.params[0].value == 90


def test_hypothesis_schema_models_a_review_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(review_action())
    )

    action = hypothesis.methods[0].steps[0].action
    assert isinstance(action, ReviewSchema)
    assert action.review_tool_calls[0].tool == "query_experiment_data"
    assert action.expected.startswith("Average temperature")


def test_hypothesis_schema_excludes_application_owned_fields() -> None:
    schema = HypothesisSchema.model_json_schema()

    assert "id" not in schema["properties"]
    assert "state" not in schema["properties"]
    assert "observed" not in schema["$defs"]["StepSchema"]["properties"]


def test_hypothesis_output_schema_is_strict() -> None:
    from gerbera_sdk.harness.agent.experiments.states import Initialisation

    def assert_strict_objects(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                assert_strict_objects(item)
            return

        if not isinstance(node, dict):
            return

        if node.get("type") == "object":
            properties = node.get("properties", {})
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(properties)

        for value in node.values():
            assert_strict_objects(value)

    assert_strict_objects(Initialisation.valid_schema)


def test_review_step_requires_an_expected_criterion() -> None:
    action = review_action()
    action["expected"] = ""

    with pytest.raises(ValidationError, match="string_too_short"):
        StepSchema.model_validate(
            {
                "description": "Review collected temperature data.",
                "action": action,
            }
        )


def test_review_step_requires_an_analysis_tool_call() -> None:
    action = review_action()
    action["review_tool_calls"] = []

    with pytest.raises(ValidationError, match="too_short"):
        StepSchema.model_validate(
            {
                "description": "Review collected temperature data.",
                "action": action,
            }
        )


def test_review_step_rejects_data_collection_fields() -> None:
    action = review_action()
    action["forward_tool_call"] = "read_temperature"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        StepSchema.model_validate(
            {
                "description": "Review collected temperature data.",
                "action": action,
            }
        )


@pytest.mark.parametrize(
    "variable_name",
    ["test scores", "StudyTime", "study-time", "study__time"],
)
def test_hypothesis_rejects_non_snake_case_variables(
    variable_name: str,
) -> None:
    data = hypothesis_data(discrete_execute_action())
    data["dependent_variables"] = [variable_name]

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        HypothesisSchema.model_validate(data)


def test_action_parameter_rejects_non_snake_case_variable() -> None:
    action = discrete_execute_action()
    action["params"][0]["variable"] = "sample count"

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        StepSchema.model_validate(
            {
                "description": "Set the sample count.",
                "action": action,
            }
        )


def test_continuous_execute_action_requires_positive_duration() -> None:
    action = continuous_execute_action()
    action["duration_seconds"] = 0

    with pytest.raises(ValidationError, match="greater_than"):
        StepSchema.model_validate(
            {
                "description": "Run the heater.",
                "action": action,
            }
        )


def test_continuous_execute_action_requires_reverse_call() -> None:
    action = continuous_execute_action()
    del action["reverse_tool_call"]

    with pytest.raises(ValidationError, match="Field required"):
        StepSchema.model_validate(
            {
                "description": "Run the heater.",
                "action": action,
            }
        )


def test_action_schema_rejects_unknown_action_type() -> None:
    action = review_action()
    action["action_type"] = "observe"

    with pytest.raises(ValidationError, match="union_tag_invalid"):
        StepSchema.model_validate(
            {
                "description": "Observe data.",
                "action": action,
            }
        )

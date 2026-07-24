import pytest
from pydantic import ValidationError

from gerbera_sdk.harness.agent.experiments.states.schema import (
    HypothesisSchema,
    StepSchema,
)


def execute_action() -> dict:
    return {
        "type": "execute",
        "independent_variables": [
            {
                "variable": "commanded_angle",
                "value": 90,
                "unit": "degrees",
            }
        ],
        "dependent_variables": [
            {
                "variable": "acknowledged_angle",
                "value": None,
                "unit": "degrees",
            }
        ],
        "setup_calls": [
            {
                "tool": "write_motor",
                "arguments": [
                    {
                        "parameter": "angle",
                        "value": 0,
                        "variable": "commanded_angle",
                    }
                ],
                "captures": [],
            }
        ],
        "trial_calls": [
            {
                "tool": "write_motor",
                "arguments": [
                    {
                        "parameter": "angle",
                        "value": 90,
                        "variable": "commanded_angle",
                    }
                ],
                "captures": [
                    {
                        "field": "angle",
                        "variable": "acknowledged_angle",
                        "unit": "degrees",
                    }
                ],
            }
        ],
        "reset_calls": [
            {
                "tool": "write_motor",
                "arguments": [
                    {
                        "parameter": "angle",
                        "value": 0,
                        "variable": None,
                    }
                ],
                "captures": [],
            }
        ],
        "repetitions": 3,
    }


def test_hypothesis_schema_models_the_generated_experiment() -> None:
    hypothesis = HypothesisSchema.model_validate(
        {
            "hypothesis": "Heating increases measured temperature.",
            "dependent_variables": ["temperature"],
            "independent_variables": ["heater_state"],
            "controlled_variables": ["room_temperature"],
            "assumptions": ["The sensor is calibrated."],
            "methods": [
                {
                    "name": "Heating test",
                    "description": "Compare temperature before and after heating.",
                    "steps": [
                        {
                            "description": "Test the servo at 90 degrees.",
                            "expected": None,
                            "action": execute_action(),
                        }
                    ],
                }
            ],
        }
    )

    action = hypothesis.methods[0].steps[0].action
    assert action.trial_calls[0].tool == "write_motor"
    assert action.independent_variables[0].value == 90
    assert action.reset_calls[0].arguments[0].value == 0
    assert action.repetitions == 3


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


def test_execute_steps_require_null_expected() -> None:
    step = StepSchema.model_validate(
        {
            "description": "Turn on the heater.",
            "action": execute_action(),
            "expected": None,
        }
    )

    assert step.expected is None


def test_review_steps_require_expected_result() -> None:
    step = StepSchema.model_validate(
        {
            "description": "Review the temperature change.",
            "action": {
                "type": "review",
                "target": "compare_temperature",
                "params": [],
            },
            "expected": "The measured temperature increased after heating.",
        }
    )

    assert step.expected == "The measured temperature increased after heating."


def test_review_steps_reject_null_expected() -> None:
    with pytest.raises(ValidationError, match="expected result"):
        StepSchema.model_validate(
            {
                "description": "Compare the analysis with the hypothesis.",
                "action": {
                    "type": "review",
                    "target": "review_temperature_analysis",
                    "params": [],
                },
                "expected": None,
            }
        )


def test_non_review_steps_reject_expected_values() -> None:
    with pytest.raises(ValidationError, match="Only review actions"):
        StepSchema.model_validate(
            {
                "description": "Turn on the heater.",
                "action": execute_action(),
                "expected": "The temperature rises.",
            }
        )


@pytest.mark.parametrize(
    "variable_name",
    ["test scores", "StudyTime", "study-time", "study__time"],
)
def test_hypothesis_rejects_non_snake_case_variables(
    variable_name: str,
) -> None:
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        HypothesisSchema.model_validate(
            {
                "hypothesis": "Study time affects test scores.",
                "dependent_variables": [variable_name],
                "independent_variables": ["study_time"],
                "controlled_variables": ["prior_knowledge"],
                "assumptions": [],
                "methods": [],
            }
        )


def test_action_parameter_rejects_non_snake_case_variable() -> None:
    action = execute_action()
    action["trial_calls"][0]["arguments"][0]["variable"] = "sample count"

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        StepSchema.model_validate(
            {
                "description": "Set the sample count.",
                "action": action,
                "expected": None,
            }
        )


def test_execute_action_requires_trial_call() -> None:
    action = execute_action()
    action["trial_calls"] = []

    with pytest.raises(ValidationError, match="too_short"):
        StepSchema.model_validate(
            {
                "description": "Run a trial.",
                "action": action,
                "expected": None,
            }
        )


def test_execute_action_requires_positive_repetitions() -> None:
    action = execute_action()
    action["repetitions"] = 0

    with pytest.raises(ValidationError, match="greater_than_equal"):
        StepSchema.model_validate(
            {
                "description": "Run a trial.",
                "action": action,
                "expected": None,
            }
        )


def test_execute_action_requires_independent_variable_binding() -> None:
    action = execute_action()
    action["trial_calls"][0]["arguments"][0]["variable"] = None

    with pytest.raises(
        ValidationError,
        match="do not manipulate independent variables",
    ):
        StepSchema.model_validate(
            {
                "description": "Run a trial.",
                "action": action,
                "expected": None,
            }
        )


def test_execute_action_requires_dependent_variable_capture() -> None:
    action = execute_action()
    action["trial_calls"][0]["captures"] = []

    with pytest.raises(
        ValidationError,
        match="do not capture dependent variables",
    ):
        StepSchema.model_validate(
            {
                "description": "Run a trial.",
                "action": action,
                "expected": None,
            }
        )

import pytest
from pydantic import ValidationError

from gerbera_sdk.harness.agent.experiments.states.initialisation import (
    HypothesisSchema,
    StepSchema,
)


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
                            "description": "Read the baseline temperature.",
                            "expected": "A valid temperature reading.",
                            "action": {
                                "type": "observe",
                                "target": "read_temperature",
                                "params": [
                                    {
                                        "variable": "sample_count",
                                        "value": 3,
                                        "unit": None,
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    )

    assert hypothesis.methods[0].steps[0].action.target == "read_temperature"
    assert hypothesis.methods[0].steps[0].action.params[0].value == 3


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


def test_expected_is_nullable_for_non_analysis_steps() -> None:
    step = StepSchema.model_validate(
        {
            "description": "Turn on the heater.",
            "action": {
                "type": "execute",
                "target": "turn_on_heater",
                "params": [
                    {"variable": "state", "value": True, "unit": None}
                ],
            },
            "expected": None,
        }
    )

    assert step.expected is None


def test_analysis_steps_require_an_expected_outcome() -> None:
    with pytest.raises(ValidationError, match="require an expected outcome"):
        StepSchema.model_validate(
            {
                "description": "Review the temperature change.",
                "action": {
                    "type": "review",
                    "target": "compare_temperature",
                    "params": [],
                },
                "expected": None,
            }
        )

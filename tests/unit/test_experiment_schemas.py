import pytest
from pydantic import TypeAdapter, ValidationError

from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis import (
    ActionSchema,
    HypothesisSchema,
    ReviewSchema,
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
        "description": "Command the motor to 90 degrees.",
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
        "description": "Run the heater for 30 seconds.",
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


def review_variable(
    variable: str,
    table_name: str,
    parameter_type: str,
    unit: str | None = None,
) -> dict:
    return {
        "variable": variable,
        "table_name": table_name,
        "unit": unit,
        "type": parameter_type,
    }


def review_action() -> dict:
    return {
        "description": "Review all collected temperature data.",
        "action_type": "review",
        "analysis_goal": (
            "Compare average temperature with the heater on and off."
        ),
        "independent_variables": [
            review_variable(
                variable="heater_state",
                table_name="heater_readings",
                parameter_type="bool",
            )
        ],
        "dependent_variables": [
            review_variable(
                variable="temperature",
                table_name="temperature_readings",
                parameter_type="float",
                unit="celsius",
            )
        ],
        "expected": "Average temperature is higher when the heater is on.",
    }


def hypothesis_data(action: dict) -> dict:
    steps = (
        [action]
        if action["action_type"] == "review"
        else [action, review_action()]
    )
    return {
        "hypothesis": "Heating increases measured temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "method": {
            "name": "heating_test",
            "description": "Compare temperature before and after heating.",
            "steps": steps,
        },
    }


def test_hypothesis_schema_models_an_execute_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(discrete_execute_action())
    )

    action = hypothesis.method.steps[0]
    assert action.forward_tool_call == "write_motor"
    assert action.params[0].value == 90


def test_hypothesis_schema_models_a_review_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(review_action())
    )

    action = hypothesis.method.steps[0]
    assert isinstance(action, ReviewSchema)
    assert action.dependent_variables[0].table_name == "temperature_readings"
    assert action.expected.startswith("Average temperature")


def test_method_requires_at_least_one_step() -> None:
    data = hypothesis_data(review_action())
    data["method"]["steps"] = []

    with pytest.raises(ValidationError, match="too_short"):
        HypothesisSchema.model_validate(data)


def test_method_requires_review_as_final_step() -> None:
    data = hypothesis_data(discrete_execute_action())
    data["method"]["steps"] = [discrete_execute_action()]

    with pytest.raises(ValidationError, match="final method step"):
        HypothesisSchema.model_validate(data)


def test_hypothesis_schema_excludes_application_owned_fields() -> None:
    schema = HypothesisSchema.model_json_schema()

    assert "id" not in schema["properties"]
    assert "state" not in schema["properties"]
    assert "observed" not in schema["$defs"]["MethodSchema"]["properties"]


def test_initialisation_output_schema_uses_new_hypothesis_schema() -> None:
    from gerbera_sdk.harness.agent.experiments.states import Initialisation

    response_schema = Initialisation.valid_schema["properties"]["response"][
        "anyOf"
    ][0]

    assert "method" in response_schema["properties"]
    assert "methods" not in response_schema["properties"]
    assert "ContinuousExecuteSchema" in Initialisation.valid_schema["$defs"]
    assert "DiscreteExecuteSchema" in Initialisation.valid_schema["$defs"]
    assert "ReviewSchema" in Initialisation.valid_schema["$defs"]


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


def test_review_action_requires_an_expected_criterion() -> None:
    action = review_action()
    action["expected"] = ""

    with pytest.raises(ValidationError, match="string_too_short"):
        ReviewSchema.model_validate(action)


def test_review_action_requires_independent_variables() -> None:
    action = review_action()
    action["independent_variables"] = []

    with pytest.raises(ValidationError, match="too_short"):
        ReviewSchema.model_validate(action)


def test_review_action_requires_dependent_variables() -> None:
    action = review_action()
    action["dependent_variables"] = []

    with pytest.raises(ValidationError, match="too_short"):
        ReviewSchema.model_validate(action)


def test_review_action_rejects_data_collection_fields() -> None:
    action = review_action()
    action["forward_tool_call"] = "read_temperature"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ReviewSchema.model_validate(action)


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
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_continuous_execute_action_requires_positive_duration() -> None:
    action = continuous_execute_action()
    action["duration_seconds"] = 0

    with pytest.raises(ValidationError, match="greater_than"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_continuous_execute_action_requires_reverse_call() -> None:
    action = continuous_execute_action()
    del action["reverse_tool_call"]

    with pytest.raises(ValidationError, match="Field required"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_action_schema_rejects_unknown_action_type() -> None:
    action = review_action()
    action["action_type"] = "observe"

    with pytest.raises(ValidationError, match="union_tag_invalid"):
        TypeAdapter(ActionSchema).validate_python(action)

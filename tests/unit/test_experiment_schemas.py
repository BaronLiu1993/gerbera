import pytest
from pydantic import TypeAdapter, ValidationError

from gerbera_sdk.events.event_key import EventKey
from gerbera_sdk.events.rules import RuleTriggerModeEnum
from gerbera_harness.agent.driver.main_loop.schema.hypothesis import (
    ActionSchema,
    AgentExecuteSchema,
    HypothesisSchema,
    ReviewSchema,
    RuleCreationSchema,
)


def action_parameter(
    tool_parameter: str,
    value: bool | int | float | str,
    parameter_type: str,
    unit: str | None = None,
) -> dict:
    return {
        "tool_parameter": tool_parameter,
        "value": value,
        "unit": unit,
        "type": parameter_type,
    }


def discrete_execute_action() -> dict:
    return {
        "description": "Command the motor to 90 degrees.",
        "action_type": "execute",
        "execution_type": "discrete",
        "start_offset_seconds": 0,
        "dependent_variables": ["acknowledged_angle"],
        "independent_variables": ["commanded_angle"],
        "forward_tool_call": "write_motor",
        "params": [
            action_parameter(
                tool_parameter="angle",
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
        "start_offset_seconds": 0,
        "duration_seconds": 30,
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "forward_tool_call": "start_heater",
        "reverse_tool_call": "stop_heater",
        "forward_tool_call_params": [
            action_parameter(
                tool_parameter="heater_state",
                value=True,
                parameter_type="bool",
            )
        ],
        "reverse_tool_call_params": [],
        "emitted_event_keys": [
            {
                "event_type": "STREAM",
                "microcontroller_id": "board-1",
                "event_name": "temperature",
            }
        ],
    }


def agent_execute_action() -> dict:
    return {
        "action_type": "execute",
        "execution_type": "agent",
        "goal": "Move within grasping range of the block.",
        "completion_criteria": "The block is centered and within reach.",
        "max_turns": 10,
        "timeout_seconds": 30,
    }


def rule_creation_action() -> dict:
    return {
        "description": "Watch for excessive temperature.",
        "action_type": "execute",
        "execution_type": "rule",
        "create_tool_call": "insert_rule",
        "delete_tool_call": "delete_rule",
        "event_key": {
            "event_type": "STREAM",
            "microcontroller_id": "board-1",
            "event_name": "temperature",
        },
        "callable": "return None",
        "operator": "greater_than",
        "expected": 20,
        "trigger_mode": "repeat",
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
    execute_action = (
        discrete_execute_action()
        if action["action_type"] == "review"
        else action
    )
    final_review_action = (
        action
        if action["action_type"] == "review"
        else review_action()
    )
    execute_steps = [
        {
            "goal": "Collect evidence for the hypothesis.",
            "action_type": "execute",
            "actions": [execute_action],
        },
    ]
    final_review = {
        "action_type": "review",
        "actions": [final_review_action],
    }
    return {
        "hypothesis": "Heating increases measured temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "method": {
            "name": "heating_test",
            "description": "Compare temperature before and after heating.",
            "execute_steps": execute_steps,
            "final_review": final_review,
        },
    }


def test_hypothesis_schema_models_an_execute_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(discrete_execute_action())
    )

    action = hypothesis.method.execute_steps[0].actions[0]
    assert action.forward_tool_call == "write_motor"
    assert action.params[0].tool_parameter == "angle"
    assert action.params[0].value == 90


def test_hypothesis_schema_models_a_rule_creation_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(rule_creation_action())
    )

    action = hypothesis.method.execute_steps[0].actions[0]
    assert isinstance(action, RuleCreationSchema)
    assert isinstance(action.event_key, EventKey)
    assert action.event_key.event_name == "temperature"
    assert action.callable == "return None"
    assert action.expected == 20.0
    assert type(action.expected) is float
    assert action.trigger_mode == RuleTriggerModeEnum.REPEAT


def test_rule_creation_accepts_once_trigger_mode() -> None:
    action = rule_creation_action()
    action["trigger_mode"] = "once"

    rule = RuleCreationSchema.model_validate(action)

    assert rule.trigger_mode == RuleTriggerModeEnum.ONCE


@pytest.mark.parametrize(
    "expected",
    ["on", "1", True, False, float("inf"), float("nan")],
)
def test_rule_creation_requires_a_finite_numeric_expected(
    expected: object,
) -> None:
    action = rule_creation_action()
    action["expected"] = expected

    with pytest.raises(ValidationError):
        RuleCreationSchema.model_validate(action)


def test_rule_creation_rejects_a_complete_function() -> None:
    action = rule_creation_action()
    action["callable"] = (
        "async def callback(mcp_url, value):\n"
        "    return value\n"
    )

    with pytest.raises(ValidationError, match="cannot define functions"):
        RuleCreationSchema.model_validate(action)


def test_rule_creation_rejects_callback_imports() -> None:
    action = rule_creation_action()
    action["callable"] = "import httpx\nreturn None"

    with pytest.raises(ValidationError, match="contain imports"):
        RuleCreationSchema.model_validate(action)


@pytest.mark.parametrize("parameter", ["mcp_url", "value"])
def test_rule_creation_rejects_reassigned_callback_parameters(
    parameter: str,
) -> None:
    action = rule_creation_action()
    action["callable"] = f"{parameter} = None\nreturn None"

    with pytest.raises(ValidationError, match="cannot reassign"):
        RuleCreationSchema.model_validate(action)


def test_rule_creation_normalizes_a_multiline_callback_body() -> None:
    action = rule_creation_action()
    action["callable"] = "  if value:\n      return value\n  return None"

    rule = RuleCreationSchema.model_validate(action)

    assert rule.callable == "if value:\n    return value\nreturn None"


def test_rule_creation_must_be_in_first_execute_group() -> None:
    data = hypothesis_data(discrete_execute_action())
    data["method"]["execute_steps"].insert(
        1,
        {
            "goal": "Create the temperature safety rule.",
            "action_type": "execute",
            "actions": [rule_creation_action()],
        },
    )

    with pytest.raises(ValidationError, match="first execute group"):
        HypothesisSchema.model_validate(data)


def test_rule_creation_can_share_the_first_execute_group() -> None:
    data = hypothesis_data(rule_creation_action())
    data["method"]["execute_steps"][0]["actions"].append(
        discrete_execute_action()
    )

    hypothesis = HypothesisSchema.model_validate(data)

    assert len(hypothesis.method.execute_steps[0].actions) == 2


def test_hypothesis_schema_models_a_review_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(review_action())
    )

    action = hypothesis.method.final_review.actions[0]
    assert isinstance(action, ReviewSchema)
    assert action.dependent_variables[0].table_name == "temperature_readings"
    assert action.expected.startswith("Average temperature")


def test_method_requires_at_least_one_execute_step() -> None:
    data = hypothesis_data(review_action())
    data["method"]["execute_steps"] = []

    with pytest.raises(ValidationError, match="too_short"):
        HypothesisSchema.model_validate(data)


def test_method_requires_final_review() -> None:
    data = hypothesis_data(discrete_execute_action())
    data["method"].pop("final_review")

    with pytest.raises(ValidationError, match="final_review"):
        HypothesisSchema.model_validate(data)


def test_execute_group_supports_parallel_actions() -> None:
    data = hypothesis_data(discrete_execute_action())
    data["method"]["execute_steps"][0]["actions"].append(
        continuous_execute_action()
    )

    hypothesis = HypothesisSchema.model_validate(data)

    assert len(hypothesis.method.execute_steps[0].actions) == 2


def test_hypothesis_schema_models_a_bounded_agent_execute_step() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(agent_execute_action())
    )

    action = hypothesis.method.execute_steps[0].actions[0]
    assert isinstance(action, AgentExecuteSchema)
    assert action.goal == "Move within grasping range of the block."
    assert action.completion_criteria == (
        "The block is centered and within reach."
    )
    assert action.max_turns == 10
    assert action.timeout_seconds == 30


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("goal", ""),
        ("completion_criteria", ""),
        ("max_turns", 0),
        ("timeout_seconds", 0),
    ],
)
def test_agent_execute_action_requires_goal_criteria_and_loop_bounds(
    field: str,
    value: object,
) -> None:
    action = agent_execute_action()
    action[field] = value

    with pytest.raises(ValidationError):
        HypothesisSchema.model_validate(hypothesis_data(action))


@pytest.mark.parametrize(
    "parallel_action",
    [discrete_execute_action(), agent_execute_action()],
)
def test_agent_execute_action_must_be_the_only_action_in_its_group(
    parallel_action: dict,
) -> None:
    data = hypothesis_data(agent_execute_action())
    data["method"]["execute_steps"][0]["actions"].append(parallel_action)

    with pytest.raises(ValidationError):
        HypothesisSchema.model_validate(data)


def test_continuous_execute_action_declares_emitted_event_keys() -> None:
    hypothesis = HypothesisSchema.model_validate(
        hypothesis_data(continuous_execute_action())
    )

    action = hypothesis.method.execute_steps[0].actions[0]
    assert action.emitted_event_keys == [
        EventKey(
            event_type="STREAM",
            microcontroller_id="board-1",
            event_name="temperature",
        )
    ]


def test_hypothesis_schema_excludes_application_owned_fields() -> None:
    schema = HypothesisSchema.model_json_schema()

    assert "id" not in schema["properties"]
    assert "state" not in schema["properties"]
    assert "observed" not in schema["$defs"]["MethodSchema"]["properties"]


def test_hypothesis_output_schema_uses_current_action_schemas() -> None:
    schema = HypothesisSchema.model_json_schema()

    assert "method" in schema["properties"]
    assert "methods" not in schema["properties"]
    assert "ContinuousExecuteSchema" in schema["$defs"]
    assert "DiscreteExecuteSchema" in schema["$defs"]
    assert "AgentExecuteSchema" in schema["$defs"]
    assert "RuleCreationSchema" in schema["$defs"]
    assert "ReviewSchema" in schema["$defs"]


def test_trigger_mode_schema_is_a_plain_enum_reference() -> None:
    trigger_mode_schema = HypothesisSchema.model_json_schema()["$defs"][
        "RuleCreationSchema"
    ]["properties"]["trigger_mode"]

    assert trigger_mode_schema == {
        "$ref": "#/$defs/RuleTriggerModeEnum",
    }


def test_hypothesis_output_schema_is_strict() -> None:
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

    assert_strict_objects(HypothesisSchema.model_json_schema())


def test_hypothesis_output_schema_uses_supported_union_keywords() -> None:
    def assert_no_discriminated_union_keywords(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                assert_no_discriminated_union_keywords(item)
            return

        if not isinstance(node, dict):
            return

        assert "discriminator" not in node
        assert "oneOf" not in node

        for value in node.values():
            assert_no_discriminated_union_keywords(value)

    assert_no_discriminated_union_keywords(
        HypothesisSchema.model_json_schema()
    )


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


def test_action_parameter_rejects_invalid_tool_parameter() -> None:
    action = discrete_execute_action()
    action["params"][0]["tool_parameter"] = "servo angle"

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_continuous_execute_action_requires_positive_duration() -> None:
    action = continuous_execute_action()
    action["duration_seconds"] = 0

    with pytest.raises(ValidationError, match="greater_than"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_execute_action_requires_non_negative_start_offset() -> None:
    action = discrete_execute_action()
    action["start_offset_seconds"] = -1

    with pytest.raises(ValidationError, match="greater_than_equal"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_continuous_execute_action_requires_reverse_call() -> None:
    action = continuous_execute_action()
    del action["reverse_tool_call"]

    with pytest.raises(ValidationError, match="Field required"):
        HypothesisSchema.model_validate(hypothesis_data(action))


def test_action_schema_rejects_unknown_action_type() -> None:
    action = review_action()
    action["action_type"] = "observe"

    with pytest.raises(ValidationError, match="literal_error"):
        TypeAdapter(ActionSchema).validate_python(action)

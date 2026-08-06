from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, StrictFloat, field_validator

from gerbera_sdk.events.event_key import EventKey
from gerbera_sdk.events.rules import (
    OperatorEnum,
    RuleTriggerModeEnum,
    normalize_rule_callback_body,
)

from gerbera_harness.agent.driver.main_loop.schema.utils import (
    SnakeCaseVariable,
    StrictSchema,
)

# Type Schemas
class ActionTypeEnum(str, Enum):
    EXECUTE = "execute"
    REVIEW = "review"


class ParameterTypeSchema(str, Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"


# Execute Action Schema
class ExecutionTypeEnum(str, Enum):
    AGENT = "agent"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    RULE = "rule"

class ExecuteActionParameterSchema(StrictSchema):
    variable: SnakeCaseVariable
    value: bool | int | float | str
    unit: str | None
    type: ParameterTypeSchema


class RuleCreationSchema(StrictSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["rule"]
    create_tool_call: str = Field(min_length=1)
    delete_tool_call: str = Field(min_length=1)
    event_key: EventKey
    callable: str = Field(
        min_length=1,
        description=(
            "Python statements for the body of "
            "async callback(mcp_url, value). The runtime imports httpx and "
            "fastmcp.Client, injects the configured MCP URL, and passes the "
            "watched sensor value as a finite float. Do not include imports, "
            "the function definition, outer indentation, or assignments to "
            "mcp_url or value."
        ),
    )
    operator: OperatorEnum
    expected: Annotated[
        StrictFloat,
        Field(allow_inf_nan=False),
    ]
    trigger_mode: RuleTriggerModeEnum

    @field_validator("callable")
    @classmethod
    def validate_callable_body(cls, value: str) -> str:
        return normalize_rule_callback_body(value)


class AgentExecuteSchema(StrictSchema):
    action_type: Literal["execute"]
    execution_type: Literal["agent"]
    goal: str = Field(min_length=1)
    completion_criteria: str = Field(min_length=1)
    max_turns: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class ContinuousExecuteSchema(StrictSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["continuous"]
    start_offset_seconds: float = Field(
        ge=0,
        description=(
            "Seconds after the execution group begins before this action starts."
        ),
    )
    duration_seconds: float = Field(gt=0)
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    forward_tool_call: str = Field(min_length=1)
    reverse_tool_call: str = Field(min_length=1)
    forward_tool_call_params: list[ExecuteActionParameterSchema]
    reverse_tool_call_params: list[ExecuteActionParameterSchema]
    emitted_event_keys: list[EventKey] = Field(
        description=(
            "Event channels that emit observations while this action runs."
        ),
    )


class DiscreteExecuteSchema(StrictSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["discrete"]
    start_offset_seconds: float = Field(
        ge=0,
        description=(
            "Seconds after the execution group begins before this action starts."
        ),
    )
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    forward_tool_call: str = Field(min_length=1)
    params: list[ExecuteActionParameterSchema]


# Review Schema
class ReviewVariableSchema(StrictSchema):
    variable: SnakeCaseVariable
    table_name: str
    unit: str | None
    type: ParameterTypeSchema


# this needs to change for decisions and how it loops back to which step in execute stage
class ReviewSchema(StrictSchema):
    description: str
    action_type: Literal["review"]
    analysis_goal: str = Field(
        min_length=1,
        description="Analysis to perform after data collection is complete.",
    )
    independent_variables: list[ReviewVariableSchema] = Field(min_length=1)
    dependent_variables: list[ReviewVariableSchema] = Field(min_length=1)
    expected: str = Field(
        min_length=1,
        description=(
            "Expected result or acceptance criterion to compare with the "
            "collected data."
        ),
    )


# Union Schemas
ExecuteSchema = (
    RuleCreationSchema
    | AgentExecuteSchema
    | ContinuousExecuteSchema
    | DiscreteExecuteSchema
)

ActionSchema = ExecuteSchema | ReviewSchema

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field
from typing_extensions import TypeAlias

from gerbera_harness.runtime.schemas.base import SnakeCaseIdentifier, HarnessSchema


class ActionTypeEnum(str, Enum):
    EXECUTE = "execute"
    REVIEW = "review"


class ParameterTypeSchema(str, Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"


class ExecutionTypeEnum(str, Enum):
    AGENT = "agent"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"


class EventKeySchema(HarnessSchema):
    event_type: str
    microcontroller_id: str
    event_name: str


class ExecuteActionParameterSchema(HarnessSchema):
    tool_parameter: SnakeCaseIdentifier = Field(
        description="Exact input name from the MCP tool schema.",
    )
    value: bool | int | float | str
    unit: str | None
    type: ParameterTypeSchema


class ContinuousExecuteSchema(HarnessSchema):
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
    dependent_variables: list[SnakeCaseIdentifier]
    independent_variables: list[SnakeCaseIdentifier]
    forward_tool_call: str = Field(min_length=1)
    reverse_tool_call: str = Field(min_length=1)
    forward_tool_call_params: list[ExecuteActionParameterSchema]
    reverse_tool_call_params: list[ExecuteActionParameterSchema]
    emitted_event_keys: list[EventKeySchema] = Field(
        description=(
            "Event channels that emit observations while this action runs."
        ),
    )


class DiscreteExecuteSchema(HarnessSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["discrete"]
    start_offset_seconds: float = Field(
        ge=0,
        description=(
            "Seconds after the execution group begins before this action starts."
        ),
    )
    dependent_variables: list[SnakeCaseIdentifier]
    independent_variables: list[SnakeCaseIdentifier]
    forward_tool_call: str = Field(min_length=1)
    params: list[ExecuteActionParameterSchema]


# class AgentExecuteSchema(HarnessSchema):
#     action_type: Literal["execute"]
#     execution_type: Literal["agent"]
#     goal: str = Field(min_length=1)
#     completion_criteria: str = Field(min_length=1)
#     max_turns: int = Field(ge=1)
#     timeout_seconds: float = Field(gt=0)


# class ReviewVariableSchema(HarnessSchema):
#     variable: SnakeCaseIdentifier
#     table_name: str
#     unit: str | None
#     type: ParameterTypeSchema


# class ReviewSchema(HarnessSchema):
#     description: str
#     action_type: Literal["review"]
#     analysis_goal: str = Field(
#         min_length=1,
#         description="Analysis to perform after data collection is complete.",
#     )
#     independent_variables: list[ReviewVariableSchema] = Field(min_length=1)
#     dependent_variables: list[ReviewVariableSchema] = Field(min_length=1)
#     expected: str = Field(
#         min_length=1,
#         description=(
#             "Expected result or acceptance criterion to compare with the "
#             "collected data."
#         ),
#     )


ActionExecuteSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)



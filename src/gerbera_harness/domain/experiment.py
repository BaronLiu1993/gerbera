"""Experiment plans produced by the agent and consumed by workflows.

Model hierarchy:
    HypothesisSchema
        -> MethodSchema
            -> ExecuteActionGroupSchema
                -> deterministic or agent execution actions
            -> ReviewActionGroupSchema
                -> ReviewSchema
"""

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from gerbera_harness.domain.schema import SnakeCaseVariable, StrictSchema


# Shared vocabulary
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


# Execution building blocks
class EventKeySchema(StrictSchema):
    event_type: str
    microcontroller_id: str
    event_name: str


class ExecuteActionParameterSchema(StrictSchema):
    tool_parameter: SnakeCaseVariable = Field(
        description="Exact input name from the MCP tool schema.",
    )
    value: bool | int | float | str
    unit: str | None
    type: ParameterTypeSchema


# Deterministic execution actions
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
    emitted_event_keys: list[EventKeySchema] = Field(
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



# Review actions
class ReviewVariableSchema(StrictSchema):
    variable: SnakeCaseVariable
    table_name: str
    unit: str | None
    type: ParameterTypeSchema


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


# # Action unions and collection constraints
# DeterministicExecuteSchema: TypeAlias = (
#     ContinuousExecuteSchema | DiscreteExecuteSchema
# )
# ExecuteSchema: TypeAlias = DeterministicExecuteSchema | AgentExecuteSchema
# ActionSchema: TypeAlias = ExecuteSchema | ReviewSchema


# DeterministicActionList: TypeAlias = Annotated[
#     list[DeterministicExecuteSchema],
#     Field(min_length=1),
# ]
# AgentActionList: TypeAlias = Annotated[
#     list[AgentExecuteSchema],
#     Field(min_length=1, max_length=1),
# ]


# Plan groups


class ReviewActionGroupSchema(StrictSchema):
    action_type: Literal["review"]
    actions: list[ReviewSchema] = Field(min_length=1, max_length=1)


# Experiment method
class MethodSchema(StrictSchema):
    description: str
    name: str
    execute_steps: list[TaskSchema] = Field(min_length=1)
    final_review: ReviewActionGroupSchema


# Root experiment plan
class HypothesisSchema(StrictSchema):
    hypothesis: str
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    controlled_variables: list[SnakeCaseVariable]
    assumptions: list[str]
    method: MethodSchema

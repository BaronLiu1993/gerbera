from enum import Enum
from typing import Annotated, Literal

from pydantic import Field

from gerbera_sdk.harness.agent.experiments.states.schema.utils import (
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
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"

class ExecuteActionParameterSchema(StrictSchema):
    variable: SnakeCaseVariable
    value: bool | int | float | str
    unit: str | None
    type: ParameterTypeSchema


class ContinuousExecuteSchema(StrictSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["continuous"]
    duration_seconds: float = Field(gt=0)
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    forward_tool_call: str = Field(min_length=1)
    reverse_tool_call: str = Field(min_length=1)
    forward_tool_call_params: list[ExecuteActionParameterSchema]
    reverse_tool_call_params: list[ExecuteActionParameterSchema]


class DiscreteExecuteSchema(StrictSchema):
    description: str
    action_type: Literal["execute"]
    execution_type: Literal["discrete"]
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

# Annotated Combined Schemas
ExecuteSchema = Annotated[
    ContinuousExecuteSchema | DiscreteExecuteSchema,
    Field(discriminator="execution_type"),
]

ActionSchema = Annotated[
    ExecuteSchema | ReviewSchema,
    Field(discriminator="action_type"),
]

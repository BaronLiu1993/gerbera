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
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"

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


ActionExecuteSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)



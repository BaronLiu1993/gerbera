from enum import Enum
from typing import Annotated, Literal

from pydantic import Field

from gerbera_harness.domain.schema import SnakeCaseVariable, StrictSchema


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


class AgentExecuteSchema(StrictSchema):
    """Adaptive closed-loop action used only when observations choose the next action."""

    action_type: Literal["execute"]
    execution_type: Literal["agent"]
    goal: str = Field(min_length=1)
    completion_criteria: str = Field(min_length=1)
    max_turns: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class ContinuousExecuteSchema(StrictSchema):
    """Deterministic action with known start, duration, and cleanup calls."""

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
    """Preferred deterministic action for one known MCP tool call."""

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


ExecuteSchema = ContinuousExecuteSchema | DiscreteExecuteSchema | AgentExecuteSchema
DeterministicExecuteSchema = ContinuousExecuteSchema | DiscreteExecuteSchema
ActionSchema = ExecuteSchema | ReviewSchema


class ExecuteActionGroupSchema(StrictSchema):
    goal: str
    action_type: Literal["execute"]
    actions: (
        Annotated[
            list[DeterministicExecuteSchema],
            Field(min_length=1),
        ]
        | Annotated[
            list[AgentExecuteSchema],
            Field(min_length=1, max_length=1),
        ]
    )


class ReviewActionGroupSchema(StrictSchema):
    action_type: Literal["review"]
    actions: list[ReviewSchema] = Field(min_length=1, max_length=1)


class MethodSchema(StrictSchema):
    description: str
    name: str
    execute_steps: list[ExecuteActionGroupSchema] = Field(min_length=1)
    final_review: ReviewActionGroupSchema


class HypothesisSchema(StrictSchema):
    hypothesis: str
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    controlled_variables: list[SnakeCaseVariable]
    # TODO(physical-constraints): Add typed physical_constraints and
    # required_observations fields. Keep static safety/capability constraints
    # separate from dynamic world state, and enforce hard constraints in the
    # action runtime rather than relying on assumptions or prompt compliance.
    assumptions: list[str]
    method: MethodSchema

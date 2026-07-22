from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gerbera_sdk.harness.agent.experiments.states.base import (
    ExperimentState,
    LoopStateEnum,
    build_valid_schema,
)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ActionTypeEnum(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"


class ActionParameterSchema(StrictSchema):
    variable: str
    value: Union[bool, int, float, str]
    unit: Optional[str]


class ActionSchema(StrictSchema):
    type: ActionTypeEnum
    target: str
    params: list[ActionParameterSchema]


class StepSchema(StrictSchema):
    description: str
    action: ActionSchema
    expected: Optional[str] = Field(
        description=(
            "Expected evidence for observe and review actions; null when the "
            "step does not evaluate evidence."
        )
    )

    @model_validator(mode="after")
    def require_expected_for_analysis(self) -> "StepSchema":
        if (
            self.action.type
            in {ActionTypeEnum.OBSERVE, ActionTypeEnum.REVIEW}
            and not self.expected
        ):
            raise ValueError(
                "Observe and review actions require an expected outcome"
            )

        return self


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[StepSchema]


class HypothesisSchema(StrictSchema):
    hypothesis: str  # This will be the goal
    dependent_variables: list[str]
    independent_variables: list[str]
    controlled_variables: list[str]
    assumptions: list[str]
    methods: list[MethodSchema]


@dataclass(frozen=True)
class Initialisation(ExperimentState):
    state: ClassVar[LoopStateEnum] = LoopStateEnum.INITIALISATION
    system_prompt: ClassVar[str] = "INITIALISATION.md"
    valid_transition_states: ClassVar[frozenset[LoopStateEnum]] = frozenset(
        {LoopStateEnum.PLAN}
    )
    valid_schema: ClassVar[dict] = build_valid_schema(
        valid_transition_states,
        HypothesisSchema,
    )

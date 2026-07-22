from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionTypeEnum(str, Enum):
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"


class ActionParameterSchema(StrictSchema):
    variable: str
    value: Union[bool, int, float, str]


class ActionSchema(StrictSchema):
    type: ActionTypeEnum
    target: str
    params: list[ActionParameterSchema]


class StepSchema(StrictSchema):
    description: str
    action: ActionSchema
    expected: Optional[str] = Field(
        description=(
            "Expected result or acceptance criterion for review actions; "
            "null for every other action type."
        )
    )

    @model_validator(mode="after")
    def validate_expected(self) -> "StepSchema":
        if self.action.type is ActionTypeEnum.REVIEW:
            if not self.expected:
                raise ValueError(
                    "Review actions must define the expected result"
                )
        elif self.expected is not None:
            raise ValueError(
                "Only review actions may define an expected value"
            )

        return self


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[StepSchema]


class HypothesisSchema(StrictSchema):
    hypothesis: str
    dependent_variables: list[str]
    independent_variables: list[str]
    controlled_variables: list[str]
    assumptions: list[str]
    methods: list[MethodSchema]

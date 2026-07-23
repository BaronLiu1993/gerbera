from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionTypeEnum(str, Enum):
    EXECUTE = "execute"
    OBSERVE = "observe"
    REVIEW = "review"


SnakeCaseVariable = Annotated[
    str,
    Field(
        pattern=SNAKE_CASE_PATTERN,
        description="Lowercase snake_case variable name.",
    ),
]
ParameterValue = bool | int | float | str


class ActionParameterSchema(StrictSchema):
    variable: SnakeCaseVariable
    value: ParameterValue


class ActionSchema(StrictSchema):
    type: ActionTypeEnum
    target: str
    params: list[ActionParameterSchema]


class StepSchema(StrictSchema):
    description: str
    action: ActionSchema
    expected: str | None = Field(
        description=(
            "Expected result or acceptance criterion for review actions; "
            "null for every other action type."
        )
    )

    @model_validator(mode="after")
    def validate_expected(self) -> "StepSchema":
        is_review = self.action.type is ActionTypeEnum.REVIEW

        if is_review and not self.expected:
            raise ValueError("Review actions must define the expected result")

        if not is_review and self.expected is not None:
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
    dependent_variables: list[SnakeCaseVariable]
    independent_variables: list[SnakeCaseVariable]
    controlled_variables: list[SnakeCaseVariable]
    assumptions: list[str]
    methods: list[MethodSchema]

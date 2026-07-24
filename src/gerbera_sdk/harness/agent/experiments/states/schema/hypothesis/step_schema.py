from pydantic import Field, model_validator

from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ActionSchema,
    ActionTypeEnum,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import StrictSchema


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

from pydantic import Field, model_validator

from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    ReviewSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import StrictSchema


ActionUnionType = (
    ContinuousExecuteSchema | DiscreteExecuteSchema | ReviewSchema
)


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[ActionUnionType] = Field(min_length=1)

    @model_validator(mode="after")
    def require_final_review(self) -> "MethodSchema":
        if not isinstance(self.steps[-1], ReviewSchema):
            raise ValueError("The final method step must be a review action")

        return self

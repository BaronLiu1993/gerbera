from typing import Literal

from pydantic import Field, model_validator

from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ExecuteSchema,
    ReviewSchema,
    RuleCreationSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.utils import StrictSchema


class ExecuteActionGroupSchema(StrictSchema):
    action_type: Literal["execute"]
    actions: list[ExecuteSchema] = Field(min_length=1)


class ReviewActionGroupSchema(StrictSchema):
    action_type: Literal["review"]
    actions: list[ReviewSchema] = Field(min_length=1, max_length=1)


ActionGroupSchema = ExecuteActionGroupSchema | ReviewActionGroupSchema


class MethodSchema(StrictSchema):
    description: str
    name: str
    steps: list[ActionGroupSchema] = Field(min_length=2)

    @model_validator(mode="after")
    def require_final_review(self) -> "MethodSchema":
        if not isinstance(self.steps[-1], ReviewActionGroupSchema):
            raise ValueError("The final action group must be a review group")

        if any(
            isinstance(group, ReviewActionGroupSchema)
            for group in self.steps[:-1]
        ):
            raise ValueError(
                "Review groups may only appear as the final method step"
            )

        for group_index, group in enumerate(self.steps[:-1]):
            if not isinstance(group, ExecuteActionGroupSchema):
                continue

            rule_actions = [
                action
                for action in group.actions
                if isinstance(action, RuleCreationSchema)
            ]
            if not rule_actions:
                continue

            if group_index != 0:
                raise ValueError(
                    "Rule creation must be in the first execute group"
                )

        return self

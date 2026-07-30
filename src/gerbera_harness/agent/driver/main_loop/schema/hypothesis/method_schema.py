from typing import Literal

from pydantic import Field, model_validator

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ExecuteSchema,
    ReviewSchema,
    RuleCreationSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class ExecuteActionGroupSchema(StrictSchema):
    action_type: Literal["execute"]
    actions: list[ExecuteSchema] = Field(min_length=1)


class ReviewActionGroupSchema(StrictSchema):
    action_type: Literal["review"]
    actions: list[ReviewSchema] = Field(min_length=1, max_length=1)


class MethodSchema(StrictSchema):
    description: str
    name: str
    execute_steps: list[ExecuteActionGroupSchema] = Field(min_length=1)
    final_review: ReviewActionGroupSchema

    @model_validator(mode="after")
    def require_rules_in_first_execute_group(self) -> "MethodSchema":
        for group_index, group in enumerate(self.execute_steps):
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

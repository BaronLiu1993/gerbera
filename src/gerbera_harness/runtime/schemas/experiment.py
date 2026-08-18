from typing import Literal

from pydantic import Field, TypeAdapter, model_validator

from gerbera_harness.runtime.schemas.base import SnakeCaseIdentifier, HarnessSchema
from gerbera_harness.runtime.schemas.execute import (
    ActionSchema,
    AgentExecuteSchema,
    ExecuteActionList,
    ReviewSchema,
)


class ExecuteActionGroupSchema(HarnessSchema):
    goal: str
    action_type: Literal["execute"]
    actions: ExecuteActionList

    @model_validator(mode="after")
    def validate_agent_is_boxed(self) -> "ExecuteActionGroupSchema":
        has_agent_action = any(
            isinstance(action, AgentExecuteSchema)
            for action in self.actions
        )
        if has_agent_action and len(self.actions) != 1:
            raise ValueError(
                "Agent execute actions must be the only action in a group"
            )
        return self


class ReviewActionGroupSchema(HarnessSchema):
    action_type: Literal["review"]
    actions: list[ReviewSchema] = Field(min_length=1, max_length=1)


action_adapter = TypeAdapter(ActionSchema)


class MethodSchema(HarnessSchema):
    description: str
    name: str
    execute_steps: list[ExecuteActionGroupSchema] = Field(min_length=1)
    final_review: ReviewActionGroupSchema


class HypothesisSchema(HarnessSchema):
    hypothesis: str
    dependent_variables: list[SnakeCaseIdentifier]
    independent_variables: list[SnakeCaseIdentifier]
    controlled_variables: list[SnakeCaseIdentifier]
    assumptions: list[str]
    method: MethodSchema

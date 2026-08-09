from typing import Annotated, Literal

from pydantic import Field, model_validator

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    DeterministicExecuteSchema,
    ReviewSchema,
    ReactionCreationSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


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

    @model_validator(mode="after")
    def require_reactions_in_first_execute_group(self) -> "MethodSchema":
        for group_index, group in enumerate(self.execute_steps):
            reaction_actions = [
                action
                for action in group.actions
                if isinstance(action, ReactionCreationSchema)
            ]
            if not reaction_actions:
                continue

            if group_index != 0:
                raise ValueError(
                    "Reaction creation must be in the first execute group"
                )

        return self

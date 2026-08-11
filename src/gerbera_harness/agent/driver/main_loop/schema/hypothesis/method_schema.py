from typing import Annotated, Literal

from pydantic import Field

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    DeterministicExecuteSchema,
    ReviewSchema,
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

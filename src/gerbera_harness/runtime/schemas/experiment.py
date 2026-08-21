from typing import Any, Literal

from pydantic import Field, TypeAdapter

from gerbera_harness.runtime.schemas.base import HarnessSchema
from gerbera_harness.runtime.schemas.execute import ActionExecuteSchema


class ExecuteActionGroupSchema(HarnessSchema):
    goal: str
    action_type: Literal["execute"]
    actions: list[ActionExecuteSchema] = Field(min_length=1)


class ReviewActionGroupSchema(HarnessSchema):
    action_type: Literal["review"]
    actions: list[dict[str, Any]] = Field(default_factory=list)


class MethodSchema(HarnessSchema):
    name: str
    description: str
    execute_steps: list[ExecuteActionGroupSchema] = Field(min_length=1)
    final_review: ReviewActionGroupSchema | None = None


class HypothesisSchema(HarnessSchema):
    hypothesis: str
    dependent_variables: list[str] = Field(default_factory=list)
    independent_variables: list[str] = Field(default_factory=list)
    controlled_variables: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    method: MethodSchema


action_adapter = TypeAdapter(ActionExecuteSchema)

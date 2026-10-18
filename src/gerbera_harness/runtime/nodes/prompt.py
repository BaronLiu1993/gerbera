from dataclasses import dataclass
import json

from pydantic import Field, JsonValue, model_validator

from gerbera_harness.runtime.contracts import ModelRequest, NodeContext
from gerbera_harness.runtime.state_machine.bindings import (
    read_pointer, validate_document, validate_json_schema,
)
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowEvent, WorkflowSchema, WorkflowState,
)


class PromptConfig(WorkflowSchema):
    prompt: str = Field(min_length=1)
    response_schema: dict[str, JsonValue]
    outcome_pointer: str | None = None
    outcome: str = "complete"

    @model_validator(mode="after")
    def validate_response_schema(self) -> "PromptConfig":
        validate_json_schema(self.response_schema)
        return self


@dataclass(frozen=True)
class PromptNode:
    config: PromptConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        await context.emit(WorkflowEvent(
            id=0, run_id=state.run_id, type="model.started",
            node=state.current_node,
            workflow=state.workflow,
        ))
        response = await context.services.model.complete(ModelRequest(
            system_prompt=self.config.prompt,
            messages=({
                "role": "user",
                "content": json.dumps({"input": context.input, "context": context.extra}),
            },),
            output_schema=self.config.response_schema,
        ))
        validate_document(response, self.config.response_schema)
        outcome = self.config.outcome
        if self.config.outcome_pointer is not None:
            outcome = read_pointer(response, self.config.outcome_pointer)
            if not isinstance(outcome, str):
                raise ValueError("Prompt outcome must be a string")
        await context.emit(WorkflowEvent(
            id=0, run_id=state.run_id, type="model.completed",
            node=state.current_node,
            workflow=state.workflow,
        ))
        return NodeResult(outcome=outcome, output=response)

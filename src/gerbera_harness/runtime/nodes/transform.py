from dataclasses import dataclass

from pydantic import Field, JsonValue

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowSchema, WorkflowState,
)


class TransformConfig(WorkflowSchema):
    constants: dict[str, JsonValue] = Field(default_factory=dict)
    outcome: str = "complete"


@dataclass(frozen=True)
class TransformNode:
    config: TransformConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        return NodeResult(
            outcome=self.config.outcome,
            output={**context.input, **self.config.constants},
        )

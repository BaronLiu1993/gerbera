from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowSchema, WorkflowState,
)


class ConditionConfig(WorkflowSchema):
    input_name: str
    operator: Literal["equals", "not_equals", "exists"] = "equals"
    value: JsonValue = None


@dataclass(frozen=True)
class ConditionNode:
    config: ConditionConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        operators = {
            "equals": lambda: context.input[self.config.input_name] == self.config.value,
            "not_equals": lambda: context.input[self.config.input_name] != self.config.value,
            "exists": lambda: self.config.input_name in context.input,
        }
        result = operators[self.config.operator]()
        return NodeResult(outcome="true" if result else "false", output=result)

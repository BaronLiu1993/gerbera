from dataclasses import dataclass

from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)


@dataclass(frozen=True)
class SubAgentResult:
    decision: ExecuteDecisionEnum
    errors: list[ExecuteErrorSchema]
    turns_completed: int

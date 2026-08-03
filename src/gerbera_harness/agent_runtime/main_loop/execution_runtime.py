from dataclasses import dataclass

from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
)
from gerbera_harness.memory import EventSchema, Memory


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecuteDecisionEnum
    requested_next_state: LoopStateEnum
    event: EventSchema


@dataclass
class ExecutionRuntime:
    memory: Memory
    mcp_url: str

    async def run_execution(self) -> ExecutionResult:
        current_task = self.memory.get_current_task()
        process = ExecutionProcess(
            mcp_url=self.mcp_url,
            actions_list=[current_task.task],
        )

        process_result = await process.run_workflow()
        decision = process_result.decision
        errors = process_result.errors

        if decision is ExecuteDecisionEnum.FAILED:
            self.memory.append_errors(errors)

        event = self.memory.append_execution_result(
            decision=decision,
            errors=errors,
        )

        return ExecutionResult(
            decision=decision,
            requested_next_state=LoopStateEnum.REVIEW,
            event=event,
        )

from dataclasses import dataclass

from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopStateEnum,
)
from gerbera_harness.memory import EventSchema, Memory


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecuteDecisionEnum
    requested_next_state: ExecuteLoopStateEnum
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

        try:
            await process.run_workflow()
        except Exception as exc:
            decision = ExecuteDecisionEnum.FAILED
            error = str(exc)
        else:
            decision = ExecuteDecisionEnum.ACCEPTED
            error = None

        event = self.memory.append_execution_result(
            decision=decision,
            error=error,
        )
        return ExecutionResult(
            decision=decision,
            requested_next_state=ExecuteLoopStateEnum.OBSERVE,
            event=event,
        )

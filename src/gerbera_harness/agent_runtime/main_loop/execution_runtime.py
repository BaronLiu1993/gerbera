from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
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
    errors: list[ExecuteErrorSchema]


@dataclass
class ExecutionRuntime:
    memory: Memory
    mcp_url: str
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    async def run_execution(self) -> ExecutionResult:
        current_task = self.memory.get_current_task()
        process = ExecutionProcess(
            mcp_url=self.mcp_url,
            actions_list=[current_task.task],
        )

        try:
            decision = await process.run_workflow()
        except Exception as exc:
            action = current_task.task.actions[0]
            execution_errors = [
                ExecuteErrorSchema(
                    event_name=current_task.task.goal,
                    event_type=ExecutionTypeEnum(action.execution_type),
                    position=self.memory.tasks.index(current_task),
                    error=str(exc),
                )
            ]
            decision = ExecuteDecisionEnum.FAILED
        else:
            execution_errors = process.errors

        self.errors.extend(execution_errors)

        event = self.memory.append_execution_result(
            decision=decision,
            errors=execution_errors,
        )

        return ExecutionResult(
            decision=decision,
            requested_next_state=LoopStateEnum.REVIEW,
            event=event,
            errors=list(execution_errors),
        )

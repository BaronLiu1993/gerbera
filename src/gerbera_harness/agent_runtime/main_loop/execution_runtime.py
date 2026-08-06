from dataclasses import dataclass, field
from functools import partial

from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states import (
    Session as SubAgentSession,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.subagent_runtime import SubAgentRuntime
from gerbera_harness.memory import EventSchema, Memory, TaskSchema


@dataclass
class _ExecutionRunState:
    current_group_index: int = 0


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecuteDecisionEnum
    requested_next_state: LoopStateEnum
    event: EventSchema
    errors: list[ExecuteErrorSchema]


@dataclass
class ExecutionRuntime:
    model: Model
    memory: Memory
    mcp_url: str
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    async def run_execution(self) -> ExecutionResult:
        action_groups = self._execution_groups()
        run_state = _ExecutionRunState()

        process = ExecutionProcess(
            mcp_url=self.mcp_url,
            actions_list=action_groups,
            agent_executor=self._execute_agent,
            on_group_started=partial(
                self._on_group_started,
                run_state,
            ),
        )

        try:
            decision = await process.run_workflow()
            execution_errors = process.errors
        except Exception as exc:
            current_group_index = run_state.current_group_index
            action = action_groups[current_group_index].actions[0]
            execution_errors = [
                ExecuteErrorSchema(
                    event_name=action_groups[current_group_index].goal,
                    event_type=ExecutionTypeEnum(action.execution_type),
                    position=current_group_index,
                    error=str(exc),
                )
            ]
            decision = ExecuteDecisionEnum.REJECTED

        self.errors.extend(execution_errors)

        current_task = self.memory.get_current_task()
        if current_task is None:
            self._on_group_started(
                run_state,
                run_state.current_group_index,
                action_groups[run_state.current_group_index],
            )

        event = self.memory.append_execution_result(
            decision=decision,
            errors=execution_errors,
        )

        if decision is ExecuteDecisionEnum.ACCEPTED:
            self.memory.complete_task()
        else:
            current_task = self.memory.get_current_task()
            if current_task is not None:
                current_task.status = "failed"

        return ExecutionResult(
            decision=decision,
            requested_next_state=LoopStateEnum.REVIEW,
            event=event,
            errors=list(execution_errors),
        )

    def _on_group_started(
        self,
        run_state: _ExecutionRunState,
        group_index: int,
        group: ExecuteActionGroupSchema,
    ) -> None:
        run_state.current_group_index = group_index
        current_task = self.memory.get_current_task()
        if group_index > 0 and current_task is not None:
            self.memory.complete_task()
            current_task = self.memory.get_current_task()
        if current_task is None:
            self.memory.tasks.append(
                TaskSchema(status="in_progress", task=group)
            )

    async def _execute_agent(
        self,
        _group_index: int,
        action: AgentExecuteSchema,
    ) -> tuple[ExecuteDecisionEnum, list[ExecuteErrorSchema]]:
        subagent_result = await SubAgentRuntime(
            session=SubAgentSession(),
            model=self.model,
            memory=self.memory,
            mcp_url=self.mcp_url,
            timeout_seconds=action.timeout_seconds,
            max_turns=action.max_turns,
        ).run_agent()
        return subagent_result.decision, subagent_result.errors

    def _execution_groups(self) -> list[ExecuteActionGroupSchema]:
        hypothesis = self.memory.current_hypothesis
        if hypothesis is not None:
            return list(hypothesis.method.execute_steps)

        groups = [
            task.task
            for task in self.memory.tasks
            if task.status == "in_progress"
        ]
        if not groups:
            raise RuntimeError(
                "Initialisation must provide execution tasks"
            )
        return groups

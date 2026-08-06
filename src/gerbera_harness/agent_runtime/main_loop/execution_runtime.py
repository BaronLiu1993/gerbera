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
from gerbera_harness.agent_runtime.subagent_context import (
    SubAgentContextBuilder,
)
from gerbera_harness.agent_runtime.subagent_runtime import SubAgentRuntime
from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    TaskSchema,
)


@dataclass
class _ExecutionRunState:
    current_group_index: int = 0
    tasks_by_group: dict[int, TaskSchema] = field(default_factory=dict)


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
            on_group_completed=partial(
                self._on_group_completed,
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

        current_position = run_state.current_group_index
        current_task = self._task_for_group(
            run_state,
            current_position,
            action_groups[current_position],
        )

        result_position = current_position
        if decision is ExecuteDecisionEnum.REJECTED:
            failed_positions = {
                error.position for error in execution_errors
            } or {current_position}
            for position in failed_positions:
                self._validate_position(position, action_groups)
                failed_task = self._task_for_group(
                    run_state,
                    position,
                    action_groups[position],
                )
                self.memory.fail_task(failed_task)
            result_position = min(failed_positions)
            current_task = run_state.tasks_by_group[result_position]

        event = self.memory.append_execution_result(
            task=current_task,
            position=result_position,
            decision=decision,
            errors=execution_errors,
        )

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
        self._task_for_group(run_state, group_index, group)

    def _on_group_completed(
        self,
        run_state: _ExecutionRunState,
        group_index: int,
        group: ExecuteActionGroupSchema,
    ) -> None:
        task = self._task_for_group(run_state, group_index, group)
        self.memory.complete_task(task)

    def _task_for_group(
        self,
        run_state: _ExecutionRunState,
        group_index: int,
        group: ExecuteActionGroupSchema,
    ) -> TaskSchema:
        existing = run_state.tasks_by_group.get(group_index)
        if existing is not None:
            return existing

        assigned_task_ids = {
            task.id for task in run_state.tasks_by_group.values()
        }
        task = next(
            (
                candidate
                for candidate in self.memory.tasks
                if candidate.status == "in_progress"
                and candidate.task == group
                and candidate.id not in assigned_task_ids
            ),
            None,
        )
        if task is None:
            task = TaskSchema(status="in_progress", task=group)
            self.memory.tasks.append(task)

        run_state.tasks_by_group[group_index] = task
        return task

    async def _execute_agent(
        self,
        group_index: int,
        action: AgentExecuteSchema,
    ) -> tuple[ExecuteDecisionEnum, list[ExecuteErrorSchema]]:
        current_task = self.memory.get_current_task()
        if current_task is None:
            raise RuntimeError("Subagent execution requires a current task")

        subagent = SubAgentRuntime(
            session=SubAgentSession(),
            model=self.model,
            context=SubAgentContextBuilder(memory=self.memory).build(
                current_task=current_task,
                workflow_position=group_index,
            ),
            mcp_url=self.mcp_url,
            timeout_seconds=action.timeout_seconds,
            max_turns=action.max_turns,
        )
        subagent_result = await subagent.run_agent()

        for observation in subagent.observations:
            self.memory.world_state_ledger.append(observation)
            self.memory.append_event(
                event_type=EventTypeEnum.WORLD_STATE_UPDATED,
                source_type=SourceTypeEnum.MODEL,
                payload={
                    "world_state": observation.model_dump(mode="json")
                },
            )
        for tool_event in subagent.tool_events:
            self.memory.append_event(
                event_type=EventTypeEnum.TOOL_CALL,
                source_type=SourceTypeEnum.MCP_TOOL,
                payload=dict(tool_event),
            )

        workflow_errors = [
            error.model_copy(update={"position": group_index})
            for error in subagent_result.errors
        ]
        return subagent_result.decision, workflow_errors

    @staticmethod
    def _validate_position(
        position: int,
        action_groups: list[ExecuteActionGroupSchema],
    ) -> None:
        if not 0 <= position < len(action_groups):
            raise IndexError(
                f"Execution position {position} is outside workflow "
                f"bounds [0, {len(action_groups)})"
            )

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

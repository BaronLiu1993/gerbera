from dataclasses import dataclass, field
from functools import partial

from gerbera_harness.agent.driver.main_loop.processes.execution_process import (
    ExecutionProcess,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
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
    Memory,
    WorldStateSchema,
)


@dataclass
class _ExecutionRunState:
    current_group_index: int = 0
    errors: list[ExecuteErrorSchema] = field(default_factory=list)
    observations: list[WorldStateSchema] = field(default_factory=list)
    tool_events: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecuteDecisionEnum
    requested_next_state: LoopStateEnum
    event: EventSchema


@dataclass
class ExecutionRuntime:
    model: Model
    memory: Memory
    mcp_url: str

    async def run_execution(self) -> ExecutionResult:
        action_groups = self._execution_groups()
        run_state = _ExecutionRunState()

        process = ExecutionProcess(
            mcp_url=self.mcp_url,
            actions_list=action_groups,
            agent_executor=partial(self._execute_agent, run_state),
            on_group_started=partial(
                self._on_group_started,
                run_state,
            ),
            on_group_completed=self._on_group_completed,
        )

        decision = await process.run_workflow()

        current_position = run_state.current_group_index
        current_task = self.memory.tasks[current_position]

        if decision is ExecuteDecisionEnum.REJECTED:
            self.memory.fail_task(current_task)

        event = self.memory.commit_execution_result(
            task=current_task,
            position=current_position,
            decision=decision,
            errors=run_state.errors,
            observations=run_state.observations,
            tool_events=[
                *process.tool_events,
                *run_state.tool_events,
            ],
        )

        return ExecutionResult(
            decision=decision,
            requested_next_state=LoopStateEnum.REVIEW,
            event=event,
        )

    def _on_group_started(
        self,
        run_state: _ExecutionRunState,
        group_index: int,
        _group: ExecuteActionGroupSchema,
    ) -> None:
        self.memory.start_task(self.memory.tasks[group_index])
        run_state.current_group_index = group_index

    def _on_group_completed(
        self,
        group_index: int,
        _group: ExecuteActionGroupSchema,
    ) -> None:
        self.memory.complete_task(self.memory.tasks[group_index])

    async def _execute_agent(
        self,
        run_state: _ExecutionRunState,
        group_index: int,
        action: AgentExecuteSchema,
    ) -> ExecuteDecisionEnum:
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

        if subagent_result.decision is ExecuteDecisionEnum.REJECTED:
            run_state.errors.extend(subagent_result.errors)
        run_state.observations.extend(subagent_result.observations)
        for event in subagent_result.tool_events:
            run_state.tool_events.append(dict(event))

        return subagent_result.decision

    def _execution_groups(self) -> list[ExecuteActionGroupSchema]:
        groups = []
        for task in self.memory.tasks:
            groups.append(task.task)
        return groups

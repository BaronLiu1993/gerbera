import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from typing import Any

from typing_extensions import TypeAlias

from gerbera_harness.runtime.session import (
    ExecuteDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.runtime.schemas.execute import (
    AgentExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.runtime.schemas.execution import (
    ExecuteErrorSchema,
)
from gerbera_harness.runtime.schemas.experiment import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.runtime.subagent.schemas import (
    Session as SubAgentSession,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.runtime.subagent.context import (
    SubAgentContextBuilder,
)
from gerbera_harness.runtime.subagent.runtime import SubAgentRuntime
from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.memory.schemas.events import (
    EventSchema,
    EventTypeEnum,
    SourceTypeEnum,
)
from gerbera_harness.memory.schemas.task import TaskSchema, TaskStatusEnum
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.memory import Memory
from gerbera_harness.tools.registry import LocalToolRegistry


DeterministicActionSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)
ProbabilisticActionSchema: TypeAlias = AgentExecuteSchema
WorkflowActionSchema: TypeAlias = (
    DeterministicActionSchema | ProbabilisticActionSchema
)

AgentExecutor = Callable[
    [int, AgentExecuteSchema],
    Awaitable[ExecuteDecisionEnum],
]
GroupStartedHandler = Callable[[int], None]
GroupCompletedHandler = Callable[[int], None]


@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]
    agent_executor: AgentExecutor
    on_group_started: GroupStartedHandler
    on_group_completed: GroupCompletedHandler
    max_task_attempts: int = 3
    tool_events: list[dict[str, object]] = field(default_factory=list)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        async with MCPClient(self.mcp_url) as client:
            tools = await client.list_tools()
            tool_names: set[str] = set()
            for tool in tools:
                tool_names.add(tool.name)

            return await self.execute_workflow(
                client,
                frozenset(tool_names),
            )

    async def execute_workflow(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
    ) -> ExecuteDecisionEnum:
        for group_index, group in enumerate(self.actions_list):
            self.on_group_started(group_index)

            decision = ExecuteDecisionEnum.REJECTED
            for _ in range(self.max_task_attempts):
                try:
                    decision = await self.execute_action_group(
                        client=client,
                        allowed_tool_names=allowed_tool_names,
                        group_index=group_index,
                        group=group,
                    )

                    print(decision)
                except Exception:
                    decision = ExecuteDecisionEnum.REJECTED

                if decision is ExecuteDecisionEnum.ACCEPTED:
                    break

            if decision is ExecuteDecisionEnum.REJECTED:
                return ExecuteDecisionEnum.REJECTED

            self.on_group_completed(group_index)

        return ExecuteDecisionEnum.ACCEPTED

    async def execute_action_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        group: ExecuteActionGroupSchema,
    ) -> ExecuteDecisionEnum:
        first_action = group.actions[0]
        if isinstance(first_action, AgentExecuteSchema):
            return await self.agent_executor(
                group_index,
                first_action,
            )

        await self.execute_deterministic_action_group(
            client=client,
            allowed_tool_names=allowed_tool_names,
            group_index=group_index,
            group=group,
        )
        return ExecuteDecisionEnum.ACCEPTED

    async def execute_deterministic_action_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        group: ExecuteActionGroupSchema,
    ) -> None:
        deterministic_actions: list[DeterministicActionSchema] = []

        for action in group.actions:
            if isinstance(
                action,
                (ContinuousExecuteSchema, DiscreteExecuteSchema),
            ):
                deterministic_actions.append(action)

        group_start = asyncio.get_running_loop().time()

        async with asyncio.TaskGroup() as task_group:
            for action in deterministic_actions:
                task_group.create_task(
                    self.execute_deterministic_action(
                        client,
                        allowed_tool_names,
                        group_index,
                        action,
                        group_start,
                    )
                )

    async def execute_deterministic_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: DeterministicActionSchema,
        group_start: float,
    ) -> None:
        start_at = group_start + action.start_offset_seconds
        now = asyncio.get_running_loop().time()
        await asyncio.sleep(max(0.0, start_at - now))

        if isinstance(action, DiscreteExecuteSchema):
            arguments = client.build_arguments(action.params)
            await self.call_tool(
                client=client,
                allowed_tool_names=allowed_tool_names,
                group_index=group_index,
                action=action,
                call_type="forward",
                tool_name=action.forward_tool_call,
                arguments=arguments,
            )
            return

        await self.execute_continuous_action(
            client,
            allowed_tool_names,
            group_index,
            action,
        )

    async def execute_continuous_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: ContinuousExecuteSchema,
    ) -> None:
        forward_arguments = client.build_arguments(
            action.forward_tool_call_params
        )
        await self.call_tool(
            client=client,
            allowed_tool_names=allowed_tool_names,
            group_index=group_index,
            action=action,
            call_type="forward",
            tool_name=action.forward_tool_call,
            arguments=forward_arguments,
        )

        try:
            await asyncio.sleep(action.duration_seconds)
        finally:
            reverse_arguments = client.build_arguments(
                action.reverse_tool_call_params
            )
            await self.call_cleanup_tool(
                client,
                allowed_tool_names,
                group_index,
                action,
                "reverse",
                action.reverse_tool_call,
                reverse_arguments,
            )

    async def call_cleanup_tool(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: WorkflowActionSchema,
        call_type: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        cleanup_task = asyncio.create_task(
            self.call_tool(
                client=client,
                allowed_tool_names=allowed_tool_names,
                group_index=group_index,
                action=action,
                call_type=call_type,
                tool_name=tool_name,
                arguments=arguments,
            )
        )

        try:
            return await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            await cleanup_task
            raise

    async def call_tool(
        self,
        *,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: WorkflowActionSchema,
        call_type: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        event = {
            "position": group_index,
            "execution_type": action.execution_type,
            "call_type": call_type,
            "tool_name": tool_name,
            "arguments": dict(arguments),
        }
        result = await client.call_tool(
            tool_name,
            arguments,
            allowed_tool_names,
        )

        self.tool_events.append(
            {
                **event,
                "status": "success",
                "result": result,
            }
        )
        return result


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
    local_tool_registry: LocalToolRegistry

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
            self._fail_task(current_task)

        for tool_event in [*process.tool_events, *run_state.tool_events]:
            self._record_tool_event(tool_event, current_task)

        event = self._record_execution_result(
            task=current_task,
            position=current_position,
            decision=decision,
            errors=run_state.errors,
            observations=run_state.observations,
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
    ) -> None:
        task = self.memory.tasks[group_index]
        task.status = TaskStatusEnum.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        self.memory.set_current_task(task.id)
        run_state.current_group_index = group_index

    def _on_group_completed(
        self,
        group_index: int,
    ) -> None:
        task = self.memory.tasks[group_index]
        task.status = TaskStatusEnum.COMPLETED
        task.finished_at = datetime.now(timezone.utc)
        if task not in self.memory.completed_tasks:
            self.memory.completed_tasks.append(task)
        self.memory.set_current_task(None)

    def _fail_task(self, task: TaskSchema) -> None:
        task.status = TaskStatusEnum.FAILED
        task.finished_at = datetime.now(timezone.utc)
        if task in self.memory.completed_tasks:
            self.memory.completed_tasks.remove(task)
        if self.memory.current_task_id == task.id:
            self.memory.set_current_task(None)

    def _record_tool_event(
        self,
        payload: dict[str, object],
        task: TaskSchema,
    ) -> EventSchema:
        return self.memory.append_event(
            EventSchema(
                session_id=self.memory.session_id,
                event_type=EventTypeEnum.TOOL_CALL,
                source_type=SourceTypeEnum.RUNTIME,
                task_id=task.id,
                payload=dict(payload),
            )
        )

    def _record_execution_result(
        self,
        *,
        task: TaskSchema,
        position: int,
        decision: ExecuteDecisionEnum,
        errors: list[ExecuteErrorSchema],
        observations: list[WorldStateSchema],
    ) -> EventSchema:
        for observation in observations:
            self.memory.append_world_state(observation)

        payload = {
            "position": position,
            "decision": decision.value,
            "step_goal": task.task.goal,
            "errors": [error.error for error in errors],
            "observations": [
                observation.model_dump(mode="json")
                for observation in observations
            ],
        }
        return self.memory.append_event(
            EventSchema(
                session_id=self.memory.session_id,
                event_type=EventTypeEnum.EXECUTION_RESULT,
                source_type=SourceTypeEnum.RUNTIME,
                task_id=task.id,
                payload=payload,
            )
        )

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
            local_tool_registry=self.local_tool_registry,
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

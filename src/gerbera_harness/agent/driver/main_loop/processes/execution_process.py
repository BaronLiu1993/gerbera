import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    RuleCreationSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.model.mcp_client import MCPClient


DeterministicActionSchema = (
    RuleCreationSchema
    | ContinuousExecuteSchema
    | DiscreteExecuteSchema
)
ExecutableActionSchema = DeterministicActionSchema | AgentExecuteSchema
ScheduledActionSchema = ContinuousExecuteSchema | DiscreteExecuteSchema
ActiveRule = tuple[int, RuleCreationSchema]
AgentExecutor = Callable[
    [int, AgentExecuteSchema],
    Awaitable[tuple[ExecuteDecisionEnum, list[ExecuteErrorSchema]]],
]
GroupStartedHandler = Callable[[int, ExecuteActionGroupSchema], None]
GroupCompletedHandler = Callable[[int, ExecuteActionGroupSchema], None]


@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]
    agent_executor: AgentExecutor | None = None
    on_group_started: GroupStartedHandler | None = None
    on_group_completed: GroupCompletedHandler | None = None
    errors: list[ExecuteErrorSchema] = field(default_factory=list)
    tool_events: list[dict[str, object]] = field(default_factory=list)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        async with MCPClient(self.mcp_url) as client:
            tools = await client.list_tools()
            tool_names: set[str] = set()
            for tool in tools:
                tool_names.add(tool.name)

            return await self._execute_workflow(
                client,
                frozenset(tool_names),
            )

    async def _execute_workflow(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
    ) -> ExecuteDecisionEnum:
        active_rules: list[ActiveRule] = []

        try:
            for group_index, group in enumerate(self.actions_list):
                if self.on_group_started is not None:
                    self.on_group_started(group_index, group)

                first_action = group.actions[0]
                if isinstance(first_action, AgentExecuteSchema):
                    if self.agent_executor is None:
                        raise RuntimeError(
                            "Agent executor is not configured"
                        )

                    agent_decision, agent_errors = await self.agent_executor(
                        group_index,
                        first_action,
                    )
                    self.errors.extend(agent_errors)
                    group_decisions = [agent_decision]
                else:
                    try:
                        group_decisions = (
                            await self._execute_deterministic_group(
                                client=client,
                                allowed_tool_names=allowed_tool_names,
                                group_index=group_index,
                                group=group,
                                active_rules=active_rules,
                            )
                        )
                    except Exception:
                        return ExecuteDecisionEnum.REJECTED

                for decision in group_decisions:
                    if decision is ExecuteDecisionEnum.REJECTED:
                        return ExecuteDecisionEnum.REJECTED

                if self.on_group_completed is not None:
                    self.on_group_completed(group_index, group)
        finally:
            await self._delete_active_rules(
                client,
                allowed_tool_names,
                active_rules,
            )

        if self.errors:
            return ExecuteDecisionEnum.REJECTED
        return ExecuteDecisionEnum.ACCEPTED

    async def _execute_deterministic_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        group: ExecuteActionGroupSchema,
        active_rules: list[ActiveRule],
    ) -> list[ExecuteDecisionEnum]:
        rules: list[RuleCreationSchema] = []
        scheduled_actions: list[ScheduledActionSchema] = []

        for action in group.actions:
            if isinstance(action, RuleCreationSchema):
                rules.append(action)
            elif isinstance(
                action,
                (ContinuousExecuteSchema, DiscreteExecuteSchema),
            ):
                scheduled_actions.append(action)

        decisions: list[ExecuteDecisionEnum] = []

        for rule in rules:
            decision = await self._create_rule(
                client,
                allowed_tool_names,
                group_index,
                rule,
                active_rules,
            )
            decisions.append(decision)

        group_start = asyncio.get_running_loop().time()
        tasks: list[asyncio.Task[ExecuteDecisionEnum]] = []

        async with asyncio.TaskGroup() as task_group:
            for action in scheduled_actions:
                task = task_group.create_task(
                    self._execute_scheduled_action(
                        client,
                        allowed_tool_names,
                        group_index,
                        action,
                        group_start,
                    )
                )
                tasks.append(task)

        for task in tasks:
            decisions.append(task.result())

        return decisions

    async def _create_rule(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        rule: RuleCreationSchema,
        active_rules: list[ActiveRule],
    ) -> ExecuteDecisionEnum:
        arguments = {
            **rule.event_key.model_dump(),
            "expected_value": rule.expected,
            "operator": rule.operator.value,
            "callback_body": rule.callable,
            "trigger_mode": rule.trigger_mode.value,
        }

        try:
            await self._call_tool(
                client=client,
                allowed_tool_names=allowed_tool_names,
                group_index=group_index,
                action=rule,
                call_type="create_rule",
                tool_name=rule.create_tool_call,
                arguments=arguments,
            )
        except Exception as exc:
            self._append_error(group_index, rule, str(exc))
            raise

        active_rules.append((group_index, rule))
        return ExecuteDecisionEnum.ACCEPTED

    async def _execute_scheduled_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: ScheduledActionSchema,
        group_start: float,
    ) -> ExecuteDecisionEnum:
        try:
            start_at = group_start + action.start_offset_seconds
            now = asyncio.get_running_loop().time()
            await asyncio.sleep(max(0.0, start_at - now))

            if isinstance(action, DiscreteExecuteSchema):
                arguments = client.build_arguments(action.params)
                await self._call_tool(
                    client=client,
                    allowed_tool_names=allowed_tool_names,
                    group_index=group_index,
                    action=action,
                    call_type="forward",
                    tool_name=action.forward_tool_call,
                    arguments=arguments,
                )
                return ExecuteDecisionEnum.ACCEPTED

            return await self._execute_continuous_action(
                client,
                allowed_tool_names,
                group_index,
                action,
            )
        except Exception as exc:
            self._append_error(group_index, action, str(exc))
            raise

    async def _execute_continuous_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: ContinuousExecuteSchema,
    ) -> ExecuteDecisionEnum:
        forward_arguments = client.build_arguments(
            action.forward_tool_call_params
        )
        await self._call_tool(
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
            await self._call_cleanup_tool(
                client,
                allowed_tool_names,
                group_index,
                action,
                "reverse",
                action.reverse_tool_call,
                reverse_arguments,
            )

        return ExecuteDecisionEnum.ACCEPTED

    async def _delete_active_rules(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        active_rules: list[ActiveRule],
    ) -> None:
        for group_index, rule in reversed(active_rules):
            try:
                await self._call_cleanup_tool(
                    client,
                    allowed_tool_names,
                    group_index,
                    rule,
                    "delete_rule",
                    rule.delete_tool_call,
                    rule.event_key.model_dump(),
                )
            except Exception as exc:
                self._append_error(
                    group_index,
                    rule,
                    f"Rule cleanup failed: {exc}",
                )

    async def _call_cleanup_tool(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: ExecutableActionSchema,
        call_type: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        cleanup_task = asyncio.create_task(
            self._call_tool(
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

    async def _call_tool(
        self,
        *,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        action: ExecutableActionSchema,
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
        try:
            result = await client.call_tool(
                tool_name,
                arguments,
                allowed_tool_names,
            )
        except Exception as exc:
            self.tool_events.append(
                {
                    **event,
                    "status": "failed",
                    "result": None,
                    "error": str(exc),
                }
            )
            raise

        self.tool_events.append(
            {
                **event,
                "status": "success",
                "result": result,
                "error": None,
            }
        )
        return result

    def _append_error(
        self,
        group_index: int,
        action: ExecutableActionSchema,
        error: str,
    ) -> None:
        group = self.actions_list[group_index]
        self.errors.append(
            ExecuteErrorSchema(
                event_name=group.goal,
                event_type=ExecutionTypeEnum(action.execution_type),
                position=group_index,
                error=error,
            )
        )

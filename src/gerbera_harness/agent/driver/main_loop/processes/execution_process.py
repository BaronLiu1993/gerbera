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


@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]
    agent_executor: AgentExecutor | None = None
    on_group_started: GroupStartedHandler | None = None
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        self._validate_workflow()

        try:
            async with MCPClient(self.mcp_url) as client:
                tools = await client.list_tools()
                allowed_tool_names = frozenset(tool.name for tool in tools)
                return await self._execute_workflow(
                    client,
                    allowed_tool_names,
                )
        except Exception as exc:
            first_action = self.actions_list[0].actions[0]
            self._append_error(0, first_action, str(exc))
            return ExecuteDecisionEnum.REJECTED

    def _validate_workflow(self) -> None:
        if not self.actions_list:
            raise ValueError(
                "ExecutionProcess requires deterministic action groups"
            )

        supported_types = (
            RuleCreationSchema,
            AgentExecuteSchema,
            ContinuousExecuteSchema,
            DiscreteExecuteSchema,
        )

        for group_index, group in enumerate(self.actions_list):
            if not isinstance(group, ExecuteActionGroupSchema):
                raise ValueError(
                    "ExecutionProcess requires deterministic action groups"
                )

            if not group.actions:
                raise ValueError(
                    "ExecutionProcess requires non-empty action groups"
                )

            agent_actions = [
                action
                for action in group.actions
                if isinstance(action, AgentExecuteSchema)
            ]
            if agent_actions and (
                len(agent_actions) != 1 or len(group.actions) != 1
            ):
                raise ValueError(
                    "An agent action must be the only action in its "
                    "execute group"
                )

            for action in group.actions:
                if not isinstance(action, supported_types):
                    raise ValueError(
                        "ExecutionProcess received an unsupported action"
                    )

                if (
                    isinstance(action, AgentExecuteSchema)
                    and self.agent_executor is None
                ):
                    raise ValueError(
                        "ExecutionProcess only accepts deterministic actions "
                        "without an agent executor"
                    )

                if (
                    isinstance(action, RuleCreationSchema)
                    and group_index != 0
                ):
                    raise ValueError(
                        "Rule creation must be in the first execute group"
                    )

    async def _execute_workflow(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
    ) -> ExecuteDecisionEnum:
        active_rules: list[ActiveRule] = []
        decisions: list[ExecuteDecisionEnum] = []

        try:
            for group_index, group in enumerate(self.actions_list):
                previous_error_count = len(self.errors)

                try:
                    if self.on_group_started is not None:
                        self.on_group_started(group_index, group)

                    first_action = group.actions[0]
                    if isinstance(first_action, AgentExecuteSchema):
                        if self.agent_executor is None:
                            raise RuntimeError(
                                "Agent executor is not configured"
                            )
                        agent_decision, agent_errors = (
                            await self.agent_executor(
                                group_index,
                                first_action,
                            )
                        )
                        self.errors.extend(agent_errors)
                        group_decisions = [agent_decision]
                    else:
                        group_decisions = await self._execute_group(
                            client,
                            allowed_tool_names,
                            group_index,
                            group,
                            active_rules,
                        )
                except Exception as exc:
                    if len(self.errors) == previous_error_count:
                        self._append_error(
                            group_index,
                            group.actions[0],
                            str(exc),
                        )
                    return ExecuteDecisionEnum.REJECTED

                decisions.extend(group_decisions)
                if any(
                    decision is not ExecuteDecisionEnum.ACCEPTED
                    for decision in group_decisions
                ):
                    if len(self.errors) == previous_error_count:
                        self._append_error(
                            group_index,
                            first_action,
                            "Action group did not complete",
                        )
                    return ExecuteDecisionEnum.REJECTED
        finally:
            await self._delete_active_rules(
                client,
                allowed_tool_names,
                active_rules,
            )

        return self._build_decision(decisions)

    async def _execute_group(
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
            await client.call_tool(
                rule.create_tool_call,
                arguments,
                allowed_tool_names,
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
                await client.call_tool(
                    action.forward_tool_call,
                    arguments,
                    allowed_tool_names,
                )
                return ExecuteDecisionEnum.ACCEPTED

            return await self._execute_continuous_action(
                client,
                allowed_tool_names,
                action,
            )
        except Exception as exc:
            self._append_error(group_index, action, str(exc))
            raise

    async def _execute_continuous_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: ContinuousExecuteSchema,
    ) -> ExecuteDecisionEnum:
        forward_arguments = client.build_arguments(
            action.forward_tool_call_params
        )
        await client.call_tool(
            action.forward_tool_call,
            forward_arguments,
            allowed_tool_names,
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
                    rule.delete_tool_call,
                    rule.event_key.model_dump(),
                )
            except Exception as exc:
                self._append_error(
                    group_index,
                    rule,
                    f"Rule cleanup failed: {exc}",
                )

    @staticmethod
    async def _call_cleanup_tool(
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        cleanup_task = asyncio.create_task(
            client.call_tool(
                tool_name,
                arguments,
                allowed_tool_names,
            )
        )

        try:
            return await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            await cleanup_task
            raise

    def _build_decision(
        self,
        decisions: list[ExecuteDecisionEnum],
    ) -> ExecuteDecisionEnum:
        if not decisions:
            self._append_incomplete_actions_error()
            return ExecuteDecisionEnum.REJECTED

        if self.errors:
            return ExecuteDecisionEnum.REJECTED

        for decision in decisions:
            if decision is not ExecuteDecisionEnum.ACCEPTED:
                self._append_incomplete_actions_error()
                return ExecuteDecisionEnum.REJECTED

        return ExecuteDecisionEnum.ACCEPTED

    def _append_incomplete_actions_error(self) -> None:
        if self.errors:
            return

        self.errors.append(
            ExecuteErrorSchema(
                event_name="deterministic_actions",
                event_type=ExecutionTypeEnum.DISCRETE,
                position=0,
                error="Not all deterministic actions completed",
            )
        )

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

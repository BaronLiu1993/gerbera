import asyncio
from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    RuleCreationSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execute_decision import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)

from gerbera_harness.agent.driver.subloop.schema.act import ToolCallStatusEnum
from gerbera_harness.agent.model.mcp_client import MCPClient

@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    async def run_workflow(self) -> ExecuteDecisionEnum:
        if not self._verify_valid_execute_actions():
            raise ValueError("ExecutionProcess requires execute action groups")
        self._validate_rule_placement()

        try:
            decision = await self._run_validated_workflow()
        except Exception as exc:
            self._append_error(0, str(exc))
            decision = ExecuteDecisionEnum.FAILED

        if self.errors:
            decision = ExecuteDecisionEnum.FAILED

        return decision

    async def _run_validated_workflow(self) -> ExecuteDecisionEnum:

        async with MCPClient(self.mcp_url) as client:

            # Get Available Tools and Then Use It as a Check
            available_tools = await client.list_tools()
            allowed_tool_names = frozenset(
                tool.name for tool in available_tools
            )
            active_rules: list[RuleCreationSchema] = []
            action_statuses: list[ToolCallStatusEnum] = []

            try:
                for group_index, group in enumerate(self.actions_list):
                    action_statuses.extend(
                        await self._execute_group(
                            client,
                            allowed_tool_names,
                            group,
                            active_rules,
                        )
                    )
            except Exception as exc:
                self._append_error(
                    group_index,
                    f"Execution group {group_index} failed",
                )
                return ExecuteDecisionEnum.FAILED
            finally:
                await self._delete_active_rules(
                    client,
                    allowed_tool_names,
                    active_rules,
                )

            return self._build_decision(action_statuses)

    def _build_decision(
        self,
        action_statuses: list[ToolCallStatusEnum],
    ) -> ExecuteDecisionEnum:
        if action_statuses and all(
            status is ToolCallStatusEnum.SUCCESS
            for status in action_statuses
        ):
            return ExecuteDecisionEnum.ACCEPTED

        if not self.errors:
            self.errors.append(
                ExecuteErrorSchema(
                    event_name="deterministic_actions",
                    event_type=ExecutionTypeEnum.DISCRETE,
                    position=0,
                    error="Not all deterministic actions completed",
                )
            )
        return ExecuteDecisionEnum.FAILED

    def _append_error(
        self,
        position: int,
        error: str,
    ) -> None:
        group = self.actions_list[position]
        action = group.actions[0]
        self.errors.append(
            ExecuteErrorSchema(
                event_name=group.goal,
                event_type=ExecutionTypeEnum(action.execution_type),
                position=position,
                error=error,
            )
        )

    async def _execute_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group: ExecuteActionGroupSchema,
        active_rules: list[RuleCreationSchema],
    ) -> list[ToolCallStatusEnum]:
        rule_actions = [
            action
            for action in group.actions
            if isinstance(action, RuleCreationSchema)
        ]
        ordinary_actions = [
            action
            for action in group.actions
            if not isinstance(action, RuleCreationSchema)
        ]

        action_statuses = [
            await self._create_rule(
                client,
                allowed_tool_names,
                action,
                active_rules,
            )
            for action in rule_actions
        ]

        group_start = asyncio.get_running_loop().time()

        action_tasks: list[asyncio.Task[ToolCallStatusEnum]] = []
        async with asyncio.TaskGroup() as task_group:
            for action in ordinary_actions:
                action_tasks.append(
                    task_group.create_task(
                        self._execute_task(
                            client,
                            allowed_tool_names,
                            action,
                            group_start,
                        )
                    )
                )

        action_statuses.extend(task.result() for task in action_tasks)
        return action_statuses

    async def _create_rule(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: RuleCreationSchema,
        active_rules: list[RuleCreationSchema],
    ) -> ToolCallStatusEnum:
        await client.call_tool(
            action.create_tool_call,
            self._build_rule_create_arguments(action),
            allowed_tool_names,
        )
        active_rules.append(action)
        return ToolCallStatusEnum.SUCCESS

    async def _execute_task(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: (
            AgentExecuteSchema
            | ContinuousExecuteSchema
            | DiscreteExecuteSchema
        ),
        group_start: float,
    ) -> ToolCallStatusEnum:
        start_at = group_start + action.start_offset_seconds
        delay = max(0.0, start_at - asyncio.get_running_loop().time())

        await asyncio.sleep(delay)

        if isinstance(action, AgentExecuteSchema):
            raise NotImplementedError(
                "Agent execute loops are not implemented yet"
            )

        if isinstance(action, DiscreteExecuteSchema):
            await client.call_tool(
                action.forward_tool_call,
                client.build_arguments(action.params),
                allowed_tool_names,
            )
            return ToolCallStatusEnum.SUCCESS
        else:
            await client.call_tool(
                action.forward_tool_call,
                client.build_arguments(action.forward_tool_call_params),
                allowed_tool_names,
            )

        try:
            await asyncio.sleep(action.duration_seconds)
        finally:
            await self._call_reverse_tool(
                client,
                allowed_tool_names,
                action.reverse_tool_call,
                client.build_arguments(action.reverse_tool_call_params),
            )

        return ToolCallStatusEnum.SUCCESS

    async def _call_reverse_tool(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        reverse_task = asyncio.create_task(
            client.call_tool(
                tool_name,
                arguments,
                allowed_tool_names,
            )
        )

        try:
            return await asyncio.shield(reverse_task)
        except asyncio.CancelledError:
            await reverse_task
            raise

    async def _delete_active_rules(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        active_rules: list[RuleCreationSchema],
    ) -> None:
        for action in reversed(active_rules):
            await self._call_reverse_tool(
                client,
                allowed_tool_names,
                action.delete_tool_call,
                self._build_rule_event_arguments(action),
            )

    @staticmethod
    def _build_rule_event_arguments(
        action: RuleCreationSchema,
    ) -> dict[str, str]:
        return action.event_key.model_dump()

    @classmethod
    def _build_rule_create_arguments(
        cls,
        action: RuleCreationSchema,
    ) -> dict[str, Any]:
        return {
            **cls._build_rule_event_arguments(action),
            "expected_value": action.expected,
            "operator": action.operator.value,
            "callback_body": action.callable,
            "trigger_mode": action.trigger_mode.value,
        }

    def _verify_valid_execute_actions(self) -> bool:
        if not self.actions_list:
            return False

        for group in self.actions_list:
            if not isinstance(group, ExecuteActionGroupSchema):
                return False

            if not group.actions:
                return False

            if not all(
                isinstance(
                    action,
                    (
                        RuleCreationSchema,
                        AgentExecuteSchema,
                        ContinuousExecuteSchema,
                        DiscreteExecuteSchema,
                    ),
                )
                for action in group.actions
            ):
                return False

        return True

    def _validate_rule_placement(self) -> None:
        for group in self.actions_list[1:]:
            if any(
                isinstance(action, RuleCreationSchema)
                for action in group.actions
            ):
                raise ValueError(
                    "Rule creation must be in the first execute group"
                )

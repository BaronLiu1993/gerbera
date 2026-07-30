import asyncio
from dataclasses import dataclass
from typing import Any

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

from gerbera_harness.agent.driver.main_loop.states import (
    DecisionEnum,
)

# ONLY CONCURRENT FOR NOW, WE NEED TO ACHIEVE PARALLELISM LATER

@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]
    decision: DecisionEnum = DecisionEnum.REJECTED


    async def run_workflow(self) -> None:
        if not self._verify_valid_execute_actions():
            raise ValueError("ExecutionProcess requires execute action groups")
        self._validate_rule_placement()

        async with MCPClient(self.mcp_url) as client:

            # Get Available Tools and Then Use It as a Check
            available_tools = await client.list_tools()
            allowed_tool_names = frozenset(
                tool.name for tool in available_tools
            )
            active_rules: list[RuleCreationSchema] = []

            try:
                for group_index, group in enumerate(self.actions_list):
                    await self._execute_group(
                        client,
                        allowed_tool_names,
                        group,
                        active_rules,
                    )
            except Exception as exc:
                raise RuntimeError(
                    f"Execution group {group_index} failed"
                ) from exc
            finally:
                await self._delete_active_rules(
                    client,
                    allowed_tool_names,
                    active_rules,
                )

    async def _execute_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group: ExecuteActionGroupSchema,
        active_rules: list[RuleCreationSchema],
    ) -> None:
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

        for action in rule_actions:
            await self._create_rule(
                client,
                allowed_tool_names,
                action,
                active_rules,
            )

        group_start = asyncio.get_running_loop().time()

        async with asyncio.TaskGroup() as task_group:
            for action in ordinary_actions:
                task_group.create_task(
                    self._execute_task(
                        client,
                        allowed_tool_names,
                        action,
                        group_start,
                    )
                )

    async def _create_rule(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: RuleCreationSchema,
        active_rules: list[RuleCreationSchema],
    ) -> None:
        await client.call_tool(
            action.create_tool_call,
            self._build_rule_create_arguments(action),
            allowed_tool_names,
        )
        active_rules.append(action)

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
    ) -> None:
        start_at = group_start + action.start_offset_seconds
        delay = max(0.0, start_at - asyncio.get_running_loop().time())

        await asyncio.sleep(delay)

        if isinstance(action, AgentExecuteSchema):
            raise NotImplementedError(
                "Agent execute loops are not implemented yet"
            )

        if isinstance(action, DiscreteExecuteSchema):
            return await client.call_tool(
                action.forward_tool_call,
                client.build_arguments(action.params),
                allowed_tool_names,
            )
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

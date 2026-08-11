import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    AgentExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.agent.model.mcp_client import MCPClient

# Action type aliases are grouped by execution semantics.
DeterministicActionSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)
ProbabilisticActionSchema: TypeAlias = AgentExecuteSchema
WorkflowActionSchema: TypeAlias = (
    DeterministicActionSchema | ProbabilisticActionSchema
)
# ActiveReaction = tuple[int, ReactionCreationSchema]

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
    # TODO: Restore detailed execution error collection after the happy path.
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
        # active_reactions: list[ActiveReaction] = []

        for group_index, group in enumerate(self.actions_list):
            self.on_group_started(group_index)

            decision = ExecuteDecisionEnum.REJECTED
            for attempt_number in range(self.max_task_attempts):
                try:
                    decision = await self.execute_action_group(
                        client=client,
                        allowed_tool_names=allowed_tool_names,
                        group_index=group_index,
                        group=group,
                        # active_reactions=active_reactions,
                    )

                    print(decision)
                except Exception:
                    decision = ExecuteDecisionEnum.REJECTED

                if decision is ExecuteDecisionEnum.ACCEPTED:
                    break

            if decision is ExecuteDecisionEnum.REJECTED:
                return ExecuteDecisionEnum.REJECTED

            self.on_group_completed(group_index)

        # await self.delete_active_reactions(
        #     client,
        #     allowed_tool_names,
        #     active_reactions,
        # )
        return ExecuteDecisionEnum.ACCEPTED

    async def execute_action_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        group: ExecuteActionGroupSchema,
        # active_reactions: list[ActiveReaction],
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
            # active_reactions=active_reactions,
        )
        return ExecuteDecisionEnum.ACCEPTED

    async def execute_deterministic_action_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group_index: int,
        group: ExecuteActionGroupSchema,
        # active_reactions: list[ActiveReaction],
    ) -> None:
        # reactions: list[ReactionCreationSchema] = []
        deterministic_actions: list[DeterministicActionSchema] = []

        for action in group.actions:
            if isinstance(
                action,
                (ContinuousExecuteSchema, DiscreteExecuteSchema),
            ):
                deterministic_actions.append(action)

            # if isinstance(action, ReactionCreationSchema):
            #     reactions.append(action)

        # for reaction in reactions:
        #     await self.create_reaction(
        #         client,
        #         allowed_tool_names,
        #         group_index,
        #         reaction,
        #         active_reactions,
        #     )

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

    # async def delete_active_reactions(
    #     self,
    #     client: MCPClient,
    #     allowed_tool_names: frozenset[str],
    #     active_reactions: list[ActiveReaction],
    # ) -> None:
    #     for group_index, reaction in reversed(active_reactions):
    #         await self.call_cleanup_tool(
    #             client,
    #             allowed_tool_names,
    #             group_index,
    #             reaction,
    #             "delete_reaction",
    #             reaction.delete_tool_call,
    #             self.event_key_arguments(reaction.event_key),
    #         )
    #
    # async def create_reaction(
    #     self,
    #     client: MCPClient,
    #     allowed_tool_names: frozenset[str],
    #     group_index: int,
    #     reaction: ReactionCreationSchema,
    #     active_reactions: list[ActiveReaction],
    # ) -> None:
    #     arguments = {
    #         **self.event_key_arguments(reaction.event_key),
    #         "expected_value": reaction.expected,
    #         "operator": reaction.operator.value,
    #         "callback_body": reaction.callable,
    #         "trigger_mode": reaction.trigger_mode.value,
    #     }
    #
    #     await self.call_tool(
    #         client=client,
    #         allowed_tool_names=allowed_tool_names,
    #         group_index=group_index,
    #         action=reaction,
    #         call_type="create_reaction",
    #         tool_name=reaction.create_tool_call,
    #         arguments=arguments,
    #     )
    #
    #     active_reactions.append((group_index, reaction))
    #
    # @staticmethod
    # def event_key_arguments(event_key: EventKeySchema) -> dict[str, str]:
    #     return {
    #         "event_type": event_key.event_type,
    #         "microcontroller_id": event_key.microcontroller_id,
    #         "event_name": event_key.event_name,
    #     }

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
        forward_arguments = client.build_arguments(action.forward_tool_call_params)
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
            reverse_arguments = client.build_arguments(action.reverse_tool_call_params)
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

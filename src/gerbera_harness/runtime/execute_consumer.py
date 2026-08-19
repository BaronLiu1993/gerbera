import asyncio
from dataclasses import dataclass
from typing import Any

from typing_extensions import TypeAlias

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.runtime.schemas.execute import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.runtime.schemas.experiment import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.tools.client import ToolClient

DeterministicActionSchema: TypeAlias = ContinuousExecuteSchema | DiscreteExecuteSchema


@dataclass
class ExecuteConsumer:
    tool_client: ToolClient

    # Run the whole thing
    async def execute_action_groups(
        self,
        action_groups: list[ExecuteActionGroupSchema],
    ) -> None:
        for group in action_groups:
            await self.execute_action_group(group)

    # Run an invidiual group
    async def execute_action_group(
        self,
        group: ExecuteActionGroupSchema,
    ) -> None:
        group_start = asyncio.get_running_loop().time()

        async with asyncio.TaskGroup() as task_group:
            for action in group.actions:
                task_group.create_task(
                    self.execute_action(
                        action=action,
                        group_start=group_start,
                    )
                )

    async def execute_action(
        self,
        *,
        action: DeterministicActionSchema,
        group_start: float,
    ) -> None:
        start_at = group_start + action.start_offset_seconds
        now = asyncio.get_running_loop().time()
        await asyncio.sleep(max(0.0, start_at - now))

        if isinstance(action, DiscreteExecuteSchema):
            await self.call_tool(
                tool_name=action.forward_tool_call,
                arguments=MCPClient.build_arguments(action.params),
            )
            return

        await self.execute_continuous_action(action)

    async def execute_continuous_action(
        self,
        action: ContinuousExecuteSchema,
    ) -> None:
        await self.call_tool(
            tool_name=action.forward_tool_call,
            arguments=MCPClient.build_arguments(
                action.forward_tool_call_params
            ),
        )

        try:
            await asyncio.sleep(action.duration_seconds)
        finally:
            await self.call_tool(
                tool_name=action.reverse_tool_call,
                arguments=MCPClient.build_arguments(
                    action.reverse_tool_call_params
                ),
            )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        await self.tool_client.call_tool(tool_name, arguments)

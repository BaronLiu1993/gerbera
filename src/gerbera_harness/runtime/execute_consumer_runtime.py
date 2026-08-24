import asyncio
from dataclasses import dataclass
from typing import Any

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)
from gerbera_harness.runtime.schemas.execute import (
    ActionExecuteSchema,
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.tools.client import ToolClient

@dataclass
class ExecuteConsumerRuntime:
    tool_client: ToolClient
    memory: Memory

    # Run the whole thing
    async def execute_actions(
        self,
        action_groups: list[list[ActionExecuteSchema]],
    ) -> None:
        for actions in action_groups:
            await self.execute_action_group(actions)

    async def execute_action_group(
        self,
        actions: list[ActionExecuteSchema],
    ) -> None:
        group_start = asyncio.get_running_loop().time()

        async with asyncio.TaskGroup() as task_group:
            for action in actions:
                task_group.create_task(
                    self.execute_action(
                        action=action,
                        group_start=group_start,
                    )
                )

    async def execute_action(
        self,
        *,
        action: ActionExecuteSchema,
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
    ) -> Any:
        result = await self.tool_client.call_tool(tool_name, arguments)
        self.memory.insert_event(
            EventSchema(
                session_id=self.memory.session_id,
                event_type=EventTypeEnum.TOOL_CALL,
                source_type=SourceTypeEnum.MCP_TOOL,
                source_name=tool_name,
                payload={
                    "arguments": arguments,
                    "result": result,
                },
                task_id=self.memory.task_state.current_task_id,
            )
        )
        return result

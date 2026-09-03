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
    tool_timeout_seconds: float = 1000.0

    # Run the whole thing
    async def execute_actions(
        self,
        action_groups: list[list[ActionExecuteSchema]],
        *,
        read_only_required: bool = False,
    ) -> list[dict[str, Any]]:
        tool_results: list[dict[str, Any]] = []
        for actions in action_groups:
            tool_results.extend(
                await self.execute_action_group(
                    actions,
                    read_only_required=read_only_required,
                )
            )
        return tool_results

    async def execute_action_group(
        self,
        actions: list[ActionExecuteSchema],
        *,
        read_only_required: bool = False,
    ) -> list[dict[str, Any]]:
        group_start = asyncio.get_running_loop().time()

        tasks: list[asyncio.Task[list[dict[str, Any]]]] = []
        async with asyncio.TaskGroup() as task_group:
            for action in actions:
                tasks.append(
                    task_group.create_task(
                        self.execute_action(
                            action=action,
                            group_start=group_start,
                            read_only_required=read_only_required,
                        )
                    )
                )

        tool_results: list[dict[str, Any]] = []
        for task in tasks:
            tool_results.extend(task.result())
        return tool_results

    async def execute_action(
        self,
        *,
        action: ActionExecuteSchema,
        group_start: float,
        read_only_required: bool = False,
    ) -> list[dict[str, Any]]:
        start_at = group_start + action.start_offset_seconds
        now = asyncio.get_running_loop().time()
        await asyncio.sleep(max(0.0, start_at - now))

        if isinstance(action, DiscreteExecuteSchema):
            tool_name = action.forward_tool_call
            arguments = MCPClient.build_arguments(action.params)
            result = await self.call_tool(
                tool_name=tool_name,
                arguments=arguments,
                read_only_required=read_only_required,
            )
            return [
                {
                    "tool_name": tool_name,
                    "status": "success",
                    "arguments": arguments,
                    "result": result,
                }
            ]

        return await self.execute_continuous_action(
            action,
            read_only_required=read_only_required,
        )

    async def execute_continuous_action(
        self,
        action: ContinuousExecuteSchema,
        *,
        read_only_required: bool = False,
    ) -> list[dict[str, Any]]:
        forward_tool_name = action.forward_tool_call
        forward_arguments = MCPClient.build_arguments(
            action.forward_tool_call_params
        )
        forward_result = await self.call_tool(
            tool_name=forward_tool_name,
            arguments=forward_arguments,
            read_only_required=read_only_required,
        )
        tool_results = [
            {
                "tool_name": forward_tool_name,
                "status": "success",
                "arguments": forward_arguments,
                "result": forward_result,
            }
        ]

        try:
            await asyncio.sleep(action.duration_seconds)
        finally:
            reverse_tool_name = action.reverse_tool_call
            reverse_arguments = MCPClient.build_arguments(
                action.reverse_tool_call_params
            )
            reverse_result = await self.call_tool(
                tool_name=reverse_tool_name,
                arguments=reverse_arguments,
                read_only_required=read_only_required,
            )
            tool_results.append(
                {
                    "tool_name": reverse_tool_name,
                    "status": "success",
                    "arguments": reverse_arguments,
                    "result": reverse_result,
                }
            )

        return tool_results

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        read_only_required: bool = False,
    ) -> Any:
        if read_only_required:
            await self.require_read_only_tool(tool_name)

        try:
            result = await asyncio.wait_for(
                self.tool_client.call_tool(tool_name, arguments),
                timeout=self.tool_timeout_seconds,
            )
        except TimeoutError:
            self.insert_tool_call_event(
                tool_name=tool_name,
                payload={
                    "status": "timeout",
                    "arguments": arguments,
                    "error_type": "TimeoutError",
                    "error_message": (
                        f"Tool call timed out after "
                        f"{self.tool_timeout_seconds} seconds"
                    ),
                },
            )
            raise
        except Exception as exc:
            self.insert_tool_call_event(
                tool_name=tool_name,
                payload={
                    "status": "failed",
                    "arguments": arguments,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            raise

        self.insert_tool_call_event(
            tool_name=tool_name,
            payload={
                "status": "success",
                "arguments": arguments,
                "result": result,
            },
        )
        return result

    async def call_read_only_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        return await self.call_tool(
            tool_name,
            arguments,
            read_only_required=True,
        )

    async def require_read_only_tool(self, tool_name: str) -> None:
        for tool in await self.tool_client.list_tools():
            if tool.name == tool_name:
                if tool.read_only is True:
                    return
                raise PermissionError(
                    f"Tool is not available in read-only runtime: {tool_name}"
                )

        raise ValueError(f"Tool is not available: {tool_name}")

    def insert_tool_call_event(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
    ) -> None:
        self.memory.insert_event(
            EventSchema(
                session_id=self.memory.session_id,
                event_type=EventTypeEnum.TOOL_CALL,
                source_type=SourceTypeEnum.MCP_TOOL,
                source_name=tool_name,
                payload=payload,
                task_id=self.memory.require_task_state().current_task_id,
            )
        )
        self.memory.rebuild_temporal_state()

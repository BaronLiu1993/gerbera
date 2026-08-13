import asyncio
from dataclasses import dataclass
from typing import Any

from gerbera_harness.domain.experiment import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.domain.adaptive import (
    ToolCallEventSchema,
    ToolCallStatusEnum,
    ToolCallTypeEnum,
)
from gerbera_harness.domain.adaptive import (
    PlanningExecuteActionSchema,
)
from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class ActRuntime:
    mcp_url: str
    timeout_seconds: float
    messages: list[dict[str, object]]
    tool_events: list[dict[str, object]]
    local_tool_registry: LocalToolRegistry
    last_event: ToolCallEventSchema | None = None

    async def run_action(
        self,
        action: PlanningExecuteActionSchema,
    ) -> ToolCallStatusEnum:
        await asyncio.sleep(action.start_offset_seconds)

        if isinstance(action, DiscreteExecuteSchema):
            return await self._execute_discrete_action(action)

        return await self._execute_continuous_action(action)

    async def _execute_discrete_action(
        self,
        action: DiscreteExecuteSchema,
    ) -> ToolCallStatusEnum:
        return await self._call_tool(
            ToolCallTypeEnum.FORWARD,
            action.forward_tool_call,
            MCPClient.build_arguments(action.params),
        )

    async def _execute_continuous_action(
        self,
        action: ContinuousExecuteSchema,
    ) -> ToolCallStatusEnum:
        await self._call_tool(
            ToolCallTypeEnum.FORWARD,
            action.forward_tool_call,
            MCPClient.build_arguments(action.forward_tool_call_params),
        )

        try:
            await asyncio.sleep(action.duration_seconds)
        except asyncio.CancelledError:
            reverse_task = asyncio.create_task(
                self._call_tool(
                    ToolCallTypeEnum.REVERSE,
                    action.reverse_tool_call,
                    MCPClient.build_arguments(
                        action.reverse_tool_call_params
                    ),
                )
            )
            try:
                await asyncio.shield(reverse_task)
            except asyncio.CancelledError:
                await reverse_task
            raise

        return await self._call_tool(
            ToolCallTypeEnum.REVERSE,
            action.reverse_tool_call,
            MCPClient.build_arguments(action.reverse_tool_call_params),
        )

    async def _call_tool(
        self,
        call_type: ToolCallTypeEnum,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolCallStatusEnum:
        if self.local_tool_registry.has(tool_name):
            result = await asyncio.wait_for(
                self.local_tool_registry.call_tool(tool_name, arguments),
                timeout=self.timeout_seconds,
            )
        else:
            result = await asyncio.wait_for(
                self._call_mcp_tool(tool_name, arguments),
                timeout=self.timeout_seconds,
            )

        return self._record_tool_success(
            call_type=call_type,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
        )

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        async with MCPClient(self.mcp_url) as client:
            tools = await client.list_tools()
            allowed_tool_names = frozenset(
                tool.name
                for tool in tools
                if tool.annotations is not None
                and tool.annotations.readOnlyHint is not None
            )
            return await client.call_tool(
                tool_name,
                arguments,
                allowed_tool_names,
            )

    def _record_tool_success(
        self,
        *,
        call_type: ToolCallTypeEnum,
        tool_name: str,
        arguments: dict[str, Any],
        result: object | None = None,
    ) -> ToolCallStatusEnum:
        event = ToolCallEventSchema(
            call_type=call_type,
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatusEnum.SUCCESS,
            result=result,
            error_message=None,
        )
        self.last_event = event
        event_payload = event.model_dump(mode="json")
        self.messages.append(
            {"role": "user", "content": event.model_dump_json()}
        )
        self.tool_events.append(event_payload)
        return ToolCallStatusEnum.SUCCESS

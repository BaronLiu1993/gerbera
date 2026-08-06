import asyncio
from dataclasses import dataclass
from typing import Any

from gerbera_harness.agent.driver.main_loop.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.agent.driver.subloop.schema.act import (
    ToolCallEventSchema,
    ToolCallStatusEnum,
    ToolCallTypeEnum,
)
from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningExecuteActionSchema,
)
from gerbera_harness.agent.model.mcp_client import MCPClient


@dataclass
class ActRuntime:
    mcp_url: str
    timeout_seconds: float
    messages: list[dict[str, object]]
    tool_events: list[dict[str, object]]
    last_event: ToolCallEventSchema | None = None

    async def run_action(
        self,
        action: PlanningExecuteActionSchema,
    ) -> ToolCallStatusEnum:
        try:
            async with MCPClient(self.mcp_url) as client:
                tools = await client.list_tools()
                allowed_tool_names = frozenset(tool.name for tool in tools)
                return await self._execute_action(
                    client,
                    allowed_tool_names,
                    action,
                )
        except TimeoutError:
            return self._emit_tool_call_event(
                call_type=ToolCallTypeEnum.FORWARD,
                tool_name=action.forward_tool_call,
                status=ToolCallStatusEnum.TIMED_OUT,
                error_message="MCP setup timed out",
            )
        except Exception as exc:
            return self._emit_tool_call_event(
                call_type=ToolCallTypeEnum.FORWARD,
                tool_name=action.forward_tool_call,
                status=ToolCallStatusEnum.FAILED,
                error_message=str(exc),
            )

    async def _execute_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: PlanningExecuteActionSchema,
    ) -> ToolCallStatusEnum:
        await asyncio.sleep(action.start_offset_seconds)

        if isinstance(action, DiscreteExecuteSchema):
            return await self._execute_discrete_action(
                client, allowed_tool_names, action
            )

        return await self._execute_continuous_action(
            client,
            allowed_tool_names,
            action,
        )

    async def _execute_discrete_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: DiscreteExecuteSchema,
    ) -> ToolCallStatusEnum:
        return await self._call_tool(
            client,
            allowed_tool_names,
            ToolCallTypeEnum.FORWARD,
            action.forward_tool_call,
            client.build_arguments(action.params),
        )

    async def _execute_continuous_action(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: ContinuousExecuteSchema,
    ) -> ToolCallStatusEnum:
        status = await self._call_tool(
            client,
            allowed_tool_names,
            ToolCallTypeEnum.FORWARD,
            action.forward_tool_call,
            client.build_arguments(action.forward_tool_call_params),
        )
        if status is not ToolCallStatusEnum.SUCCESS:
            return status

        try:
            await asyncio.sleep(action.duration_seconds)
        except asyncio.CancelledError:
            reverse_task = asyncio.create_task(
                self._call_tool(
                    client,
                    allowed_tool_names,
                    ToolCallTypeEnum.REVERSE,
                    action.reverse_tool_call,
                    client.build_arguments(action.reverse_tool_call_params),
                )
            )
            try:
                await asyncio.shield(reverse_task)
            except asyncio.CancelledError:
                await reverse_task
            raise

        return await self._call_tool(
            client,
            allowed_tool_names,
            ToolCallTypeEnum.REVERSE,
            action.reverse_tool_call,
            client.build_arguments(action.reverse_tool_call_params),
        )

    async def _call_tool(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        call_type: ToolCallTypeEnum,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolCallStatusEnum:
        try:
            result = await asyncio.wait_for(
                client.call_tool(
                    tool_name,
                    arguments,
                    allowed_tool_names,
                ),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            return self._emit_tool_call_event(
                call_type=call_type,
                tool_name=tool_name,
                arguments=arguments,
                status=ToolCallStatusEnum.TIMED_OUT,
                error_message=(
                    f"Tool call timed out after {self.timeout_seconds} seconds"
                ),
            )
        except Exception as exc:
            return self._emit_tool_call_event(
                call_type=call_type,
                tool_name=tool_name,
                arguments=arguments,
                status=ToolCallStatusEnum.FAILED,
                error_message=str(exc),
            )

        return self._emit_tool_call_event(
            call_type=call_type,
            tool_name=tool_name,
            arguments=arguments,
            status=ToolCallStatusEnum.SUCCESS,
            result=result,
        )

    def _emit_tool_call_event(
        self,
        *,
        call_type: ToolCallTypeEnum,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        status: ToolCallStatusEnum,
        result: object | None = None,
        error_message: str | None = None,
    ) -> ToolCallStatusEnum:
        event = ToolCallEventSchema(
            call_type=call_type,
            tool_name=tool_name,
            arguments=arguments or {},
            status=status,
            result=result,
            error_message=error_message,
        )
        self.last_event = event
        event_payload = event.model_dump(mode="json")
        self.messages.append(
            {"role": "user", "content": event.model_dump_json()}
        )
        self.tool_events.append(event_payload)
        return status

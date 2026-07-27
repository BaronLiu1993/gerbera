import asyncio
from dataclasses import dataclass
from typing import Any

from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.action_schema import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
    ExecuteActionParameterSchema,
)
from gerbera_sdk.harness.agent.experiments.states.schema.hypothesis.method_schema import (
    ExecuteActionGroupSchema,
)
from gerbera_sdk.harness.agent.model.mcp_client import MCPClient


@dataclass
class ExecutionProcess:
    mcp_url: str
    actions_list: list[ExecuteActionGroupSchema]

    async def run_workflow(self) -> list[list[Any]]:
        if not self._verify_valid_execute_actions():
            raise ValueError("ExecutionProcess requires execute action groups")

        async with MCPClient(self.mcp_url) as client:
            available_tools = await client.list_tools()
            allowed_tool_names = frozenset(
                tool.name for tool in available_tools
            )

            results = []
            for group_index, group in enumerate(self.actions_list):
                try:
                    group_results = await self._execute_group(
                        client,
                        allowed_tool_names,
                        group,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"Execution group {group_index} failed"
                    ) from exc

                results.append(group_results)

            return results

    async def _execute_group(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        group: ExecuteActionGroupSchema,
    ) -> list[Any]:
        group_start = asyncio.get_running_loop().time()
        action_tasks: list[asyncio.Task[Any]] = []

        async with asyncio.TaskGroup() as task_group:
            for action in group.actions:
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

        return [task.result() for task in action_tasks]

    async def _execute_task(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        action: ContinuousExecuteSchema | DiscreteExecuteSchema,
        group_start: float,
    ) -> Any:
        start_at = group_start + action.start_offset_seconds
        delay = max(0.0, start_at - asyncio.get_running_loop().time())
        await asyncio.sleep(delay)

        if isinstance(action, DiscreteExecuteSchema):
            return await self._call_tool(
                client,
                allowed_tool_names,
                action.forward_tool_call,
                self._build_arguments(action.params),
            )

        forward_result = await self._call_tool(
            client,
            allowed_tool_names,
            action.forward_tool_call,
            self._build_arguments(action.forward_tool_call_params),
        )

        reverse_result = None
        try:
            await asyncio.sleep(action.duration_seconds)
        finally:
            reverse_result = await self._call_cleanup_tool(
                client,
                allowed_tool_names,
                action.reverse_tool_call,
                self._build_arguments(action.reverse_tool_call_params),
            )

        return {
            "forward": forward_result,
            "reverse": reverse_result,
        }

    async def _call_cleanup_tool(
        self,
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        cleanup_task = asyncio.create_task(
            self._call_tool(
                client,
                allowed_tool_names,
                tool_name,
                arguments,
            )
        )

        try:
            return await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            await cleanup_task
            raise

    @staticmethod
    async def _call_tool(
        client: MCPClient,
        allowed_tool_names: frozenset[str],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        if tool_name not in allowed_tool_names:
            raise ValueError(f"MCP tool is not allowed: {tool_name}")

        result = await client.call_tool(tool_name, arguments)
        
        if result.is_error:
            raise RuntimeError(
                f"MCP tool {tool_name!r} failed: {result.content}"
            )

        return result.data

    @staticmethod
    def _build_arguments(
        parameters: list[ExecuteActionParameterSchema],
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {}

        for parameter in parameters:
            if parameter.variable in arguments:
                raise ValueError(
                    f"Duplicate MCP tool parameter: {parameter.variable}"
                )

            arguments[parameter.variable] = parameter.value

        return arguments

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
                    (ContinuousExecuteSchema, DiscreteExecuteSchema),
                )
                for action in group.actions
            ):
                return False

        return True

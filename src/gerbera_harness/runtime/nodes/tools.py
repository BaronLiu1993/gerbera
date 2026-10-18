import asyncio
from dataclasses import dataclass
import json

from pydantic import Field, JsonValue, TypeAdapter, model_validator

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.state_machine.bindings import (
    enforce_json_limit, validate_document,
)
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowEvent, WorkflowSchema, WorkflowState,
)


class ToolCall(WorkflowSchema):
    name: str = Field(min_length=1)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def decode_arguments(cls, data):
        if isinstance(data, dict) and "arguments_json" in data:
            payload = dict(data)
            if "arguments" in payload:
                raise ValueError("Specify arguments or arguments_json, not both")
            payload["arguments"] = json.loads(payload.pop("arguments_json"))
            return payload
        return data


class ToolExecutionConfig(WorkflowSchema):
    allowed_tools: tuple[str, ...] | None = None
    access: str = Field(default="all", pattern="^(all|read_only)$")
    maximum_calls: int = Field(default=20, ge=1)
    timeout_seconds: float = Field(default=30, gt=0)
    maximum_result_bytes: int = Field(default=64_000, ge=1024)


@dataclass(frozen=True)
class ToolExecutionNode:
    config: ToolExecutionConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        calls = TypeAdapter(list[ToolCall]).validate_python(context.input["calls"])
        if len(calls) > self.config.maximum_calls:
            raise ValueError("Tool call limit exceeded")
        specs = {spec.name: spec for spec in await context.services.tools.list_tools()}
        for call in calls:
            if call.name not in specs:
                raise ValueError(f"Unknown tool: {call.name}")
            spec = specs[call.name]
            allowed = self.config.allowed_tools
            if allowed is not None and call.name not in allowed:
                raise PermissionError(f"Tool is not allowed: {call.name}")
            if self.config.access == "read_only" and not spec.read_only:
                raise PermissionError(f"Tool is not read-only: {call.name}")
            validate_document(call.arguments, spec.input_schema)
        results = []
        for call in calls:
            results.append(await self.call_tool(call, state, context))
        return NodeResult(outcome="complete", output={"results": results})

    async def call_tool(
        self, call: ToolCall, state: WorkflowState, context: NodeContext,
    ) -> dict[str, JsonValue]:
        event = WorkflowEvent(
            id=0, run_id=state.run_id, type="tool.started",
            node=state.current_node, data={"name": call.name},
            workflow=state.workflow,
        )
        await context.emit(event)
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                result = await context.services.tools.call_tool(call.name, call.arguments)
            result = TypeAdapter(JsonValue).validate_python(result)
            enforce_json_limit(result, self.config.maximum_result_bytes)
        except Exception:
            await context.emit(event.model_copy(update={"type": "tool.failed"}))
            raise
        await context.emit(event.model_copy(update={"type": "tool.completed"}))
        return {"name": call.name, "result": result}

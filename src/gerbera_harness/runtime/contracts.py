from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import JsonValue

from gerbera_harness.tools.base import ToolSpec
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowEvent, WorkflowState,
)


@dataclass(frozen=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[dict[str, str], ...]
    output_schema: dict[str, JsonValue]


class ModelClient(Protocol):
    async def complete(self, request: ModelRequest) -> JsonValue: ...


class ToolSource(Protocol):
    async def list_tools(self) -> list[ToolSpec]: ...

    async def call_tool(
        self, name: str, arguments: dict[str, JsonValue],
    ) -> JsonValue: ...


class ResourceSource(Protocol):
    async def read_resource(self, uri: str) -> JsonValue: ...


EventHandler = Callable[[WorkflowEvent], Awaitable[None]]
ContextTransform = Callable[[WorkflowState], Awaitable[dict[str, JsonValue]]]


@dataclass(frozen=True)
class HarnessServices:
    model: ModelClient
    tools: ToolSource
    resources: ResourceSource | None = None


@dataclass(frozen=True)
class NodeContext:
    services: HarnessServices
    emit: EventHandler
    input: dict[str, JsonValue] = field(default_factory=dict)
    extra: dict[str, JsonValue] = field(default_factory=dict)


class WorkflowNode(Protocol):
    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult: ...

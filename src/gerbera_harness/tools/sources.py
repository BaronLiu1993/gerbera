import asyncio
from dataclasses import dataclass, field
import time

from pydantic import JsonValue, TypeAdapter

from gerbera_harness.connectors.urls import require_remote_url
from gerbera_harness.runtime.contracts import ToolSource
from gerbera_harness.runtime.state_machine.bindings import enforce_json_limit
from gerbera_harness.tools.base import ToolSpec
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass(frozen=True)
class LocalToolSource:
    registry: LocalToolRegistry = field(default_factory=LocalToolRegistry)

    async def list_tools(self) -> list[ToolSpec]:
        return self.registry.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> JsonValue:
        return await self.registry.call_tool(name, arguments)


@dataclass(frozen=True)
class McpToolSource:
    url: str
    timeout_seconds: float = 30

    async def list_tools(self) -> list[ToolSpec]:
        from fastmcp import Client

        async with Client(require_remote_url(self.url), timeout=self.timeout_seconds) as client:
            tools = await client.list_tools()
        return [ToolSpec(
            name=tool.name, description=tool.description or "",
            input_schema=tool.inputSchema,
            read_only=bool(tool.annotations and tool.annotations.readOnlyHint),
            destructive=bool(tool.annotations and tool.annotations.destructiveHint),
        ) for tool in tools]

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> JsonValue:
        from fastmcp import Client

        async with Client(require_remote_url(self.url), timeout=self.timeout_seconds) as client:
            result = await client.call_tool(name, arguments)
        if result.is_error:
            raise RuntimeError(f"Remote tool failed: {name}")
        return TypeAdapter(JsonValue).validate_python(result.data)


@dataclass
class CompositeToolSource:
    sources: tuple[ToolSource, ...]
    cache_seconds: float = 30
    maximum_result_bytes: int = 64_000
    owners: dict[str, ToolSource] = field(default_factory=dict, init=False)
    specs: tuple[ToolSpec, ...] = field(default=(), init=False)
    expires_at: float = field(default=0, init=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def list_tools(self) -> list[ToolSpec]:
        async with self.lock:
            if time.monotonic() < self.expires_at:
                return list(self.specs)
            owners = {}
            specs = []
            for source in self.sources:
                for spec in await source.list_tools():
                    if spec.name in owners:
                        raise ValueError(f"Duplicate tool name: {spec.name}")
                    owners[spec.name] = source
                    specs.append(spec)
            self.owners = owners
            self.specs = tuple(specs)
            self.expires_at = time.monotonic() + self.cache_seconds
            return list(self.specs)

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> JsonValue:
        await self.list_tools()
        if name not in self.owners:
            raise ValueError(f"Unknown tool: {name}")
        result = await self.owners[name].call_tool(name, arguments)
        result = TypeAdapter(JsonValue).validate_python(result)
        enforce_json_limit(result, self.maximum_result_bytes)
        return result

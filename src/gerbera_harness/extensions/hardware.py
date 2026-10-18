from dataclasses import dataclass

from pydantic import JsonValue

from gerbera_harness.runtime.contracts import ResourceSource, ToolSource
from gerbera_harness.runtime.extensions import HarnessRegistry
from gerbera_harness.runtime.state_machine.schemas import WorkflowState


@dataclass(frozen=True)
class HardwareContextExtension:
    tools: ToolSource
    resources: ResourceSource | None = None

    def register(self, registry: HarnessRegistry) -> None:
        registry.register_context_transform(self.context)

    async def context(self, state: WorkflowState) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "hardware_tools": [
                tool.model_dump() for tool in await self.tools.list_tools()
            ],
        }
        if self.resources is not None:
            result["hardware"] = await self.resources.read_resource("gerbera://hardware")
        return result


@dataclass(frozen=True)
class PhysicalStateProjection:
    resources: ResourceSource
    resource_uri: str = "gerbera://hardware/state"

    def register(self, registry: HarnessRegistry) -> None:
        registry.register_context_transform(self.snapshot)

    async def snapshot(self, state: WorkflowState) -> dict[str, JsonValue]:
        return {"physical_state": await self.resources.read_resource(self.resource_uri)}

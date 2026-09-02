from dataclasses import dataclass
from typing import Any

from gerbera_harness.runtime.context.base import ContextBuilder
from gerbera_harness.tools.client import ToolClient


@dataclass(frozen=True)
class TaskDecompositionContextBuilder(ContextBuilder):
    tool_client: ToolClient

    async def build_runtime_context(self) -> dict[str, object]:
        return {
            "session_id": self.memory.session_id,
            "environment_state": await self.get_current_environment_state(),
            "physical_configuration": {
                "hardware_state_by_name": await self.get_current_hardware_state(),
                "joint_state_by_movement_system": {},
            },
        }

    async def get_current_environment_state(self) -> dict[str, Any]:
        return await self.tool_client.call_tool(
            "get_current_environment_state",
            {},
        )

    async def get_current_hardware_state(self) -> dict[str, Any]:
        return await self.tool_client.call_tool(
            "get_current_hardware_state",
            {},
        )

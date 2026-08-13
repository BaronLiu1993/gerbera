from dataclasses import dataclass, field
import json
from typing import Any

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.memory.memory_schema import (
    EventStateSchema,
    HardwareConfigurationStateSchema,
    TaskStateSchema,
    TemporalStateSchema,
    WorldStateSchema,
)

@dataclass
class Memory:
    session_id: str
    user_goal: str
    world_state: WorldStateSchema
    temporal_state: TemporalStateSchema
    task_state: TaskStateSchema
    events_state: EventStateSchema
    hardware_configuration: HardwareConfigurationStateSchema
    mcp_client: MCPClient = field(init=False)

    # wire it all up later
    # Defining world state
    async def define_world_state(self) -> WorldStateSchema:
        environment_state = await self.get_current_environment_state()
        hardware_state = await self.get_current_hardware_state()

        self.world_state = WorldStateSchema(
            session_id=self.session_id,
            environment_state=environment_state,
            hardware_state=hardware_state,
            sources=[],
        )
        return self.world_state

    async def get_current_environment_state(self) -> dict[str, Any]:
        async with self.mcp_client as client:
            return await client.call_tool(
                "get_current_environment_state",
                {},
                frozenset({"get_current_environment_state"}),
            )

    async def get_current_hardware_state(self) -> dict[str, Any]:
        async with self.mcp_client as client:
            hardware_state = await client.call_tool(
                "get_current_hardware_state",
                {},
                frozenset({"get_current_hardware_state"}),
            )

        return json.loads(hardware_state)

    def define_task_state(self):
        pass

    def get_task_state(self):
        pass

    def define_hardware_configuration(self):
        pass

    def get_hardware_configuration(self):
        return self.hardware_configuration

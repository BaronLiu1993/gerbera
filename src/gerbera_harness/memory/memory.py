from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.memory.schemas import (
    EventStateSchema,
    PhysicalConfigurationStateSchema,
    TaskSchema,
    EventSchema,
    TaskStateSchema,
    TaskStatusEnum,
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
    physical_configuration: PhysicalConfigurationStateSchema
    mcp_client: MCPClient

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
            return await client.call_tool(
                "get_current_hardware_state",
                {},
                frozenset({"get_current_hardware_state"}),
            )

    def complete_task(self) -> None:
        task = self.get_current_task_state()
        task.status = TaskStatusEnum.COMPLETED
        task.finished_at = datetime.now(timezone.utc)

    def fail_task(self) -> None:
        task = self.get_current_task_state()
        task.status = TaskStatusEnum.FAILED
        task.finished_at = datetime.now(timezone.utc)

    def start_task(self) -> None:
        task = self.get_current_task_state()
        task.status = TaskStatusEnum.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        self.task_state.current_task_id = task.task_id

    def get_current_task_state(self) -> TaskSchema:
        current_task_id = self.task_state.current_task_id
        for task in self.task_state.tasks:
            if task.task_id == current_task_id:
                return task

    def get_full_task_state(self) -> TaskStateSchema:
        return self.task_state

    def insert_event(self, event: EventSchema) -> None:
        self.events_state.events.append(event)

    def get_full_events_state(self) -> list[EventSchema]:
        return list(self.events_state.events)

    def get_temporal_state(self) -> TemporalStateSchema:
        return self.temporal_state

    def rebuild_temporal_state(self, window_size: int = 20) -> TemporalStateSchema:
        # self.temporal_state.current_hardware_configuration = 
        self.temporal_state.recent_events = self.events_state.events[-window_size:]
        self.temporal_state.recent_world_states = [self.world_state][-window_size:]
        self.temporal_state.recent_task_results = (
            self.task_state.tasks[-window_size:]
        )
    #
    # def define_physical_configuration(self):
    #     pass

    # def get_hardware_configuration(self):
    #     return self.physical_configuration

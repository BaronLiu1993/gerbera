from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.memory.memory_schema import (
    EventSchema,
    EventStateSchema,
    HardwareConfigurationStateSchema,
    TaskStateSchema,
    TaskStatusEnum,
    TemporalStateSchema,
    WorldStateSchema,
    TaskSchema
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

    def get_current_task(self):
        current_task_id = self.task_state.current_task_id
        tasks = self.task_state.tasks
        for task in tasks:
            if task.task_id == current_task_id:
                return task

    def complete_task(self) -> None:
        task = self.get_current_task()
        task.status = TaskStatusEnum.COMPLETED
        task.finished_at = datetime.now(timezone.utc)

    def fail_task(self) -> None:
        task = self.get_current_task()
        task.status = TaskStatusEnum.FAILED
        task.finished_at = datetime.now(timezone.utc)

    def start_task(self) -> None:
        tasks = self.task_state.tasks
        for task in tasks:  
            if task.status == TaskStatusEnum.PENDING:
                self.task_state.current_task_id = task.task_id
                task.status = TaskStatusEnum.IN_PROGRESS
                task.finished_at = datetime.now(timezone.utc)
                return

    def add_new_task(self, task: TaskSchema) -> None:
        tasks = self.task_state.tasks
        tasks.append(task) # this task is pending

    # give agent context on what is done and more it needs to do 
    def get_current_task_state(self) -> dict[str, Any]:
        task = self.get_current_task()
        return task.model_dump(mode="json")

    def get_task_state_history(self) -> dict[str, Any]:
        return self.task_state.model_dump(mode="json")

    def add_event_state(self, event: EventSchema) -> None:
        self.events_state.events.append(event)

    def get_event_state_history(self) -> dict[str, Any]:
        return self.events_state.model_dump(mode="json")

    def define_hardware_configuration(self):
        pass

    def get_hardware_configuration(self):
        pass

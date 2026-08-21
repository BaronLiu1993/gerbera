from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from gerbera_harness.memory.schemas import (
    EventSchema,
    EventStateSchema,
    EventTypeEnum,
    PhysicalConfigurationStateSchema,
    SourceTypeEnum,
    TaskSchema,
    TaskStateSchema,
    TaskStatusEnum,
    TemporalStateSchema,
    WorldStateSchema,
)
from gerbera_harness.tools.client import ToolClient


@dataclass
class Memory:
    session_id: str
    user_goal: str
    world_state: WorldStateSchema
    temporal_state: TemporalStateSchema
    task_state: TaskStateSchema
    events_state: EventStateSchema
    physical_configuration: PhysicalConfigurationStateSchema
    tool_client: ToolClient

    """
    class EventSchema(HarnessSchema):
    session_id: str
    event_type: EventTypeEnum
    source_name: str
    payload: dict[str, Any]
    task_id: str
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    """

    
    # wire it all up later
    # Defining world state
    async def define_world_state(self) -> WorldStateSchema:
        environment_state = await self.get_current_environment_state()
        hardware_state = await self.get_current_hardware_state()
        task_id = self.task_state.current_task_id # needs to be a task that is started for observe to work
        environment_event = EventSchema(
            session_id=self.session_id,
            event_type=EventTypeEnum.WORLD_STATE_UPDATED,
            source_type=SourceTypeEnum.MCP_TOOL,
            source_name="get_current_environment_state",
            payload=environment_state,
            task_id=task_id,
        )
        hardware_event = EventSchema(
            session_id=self.session_id,
            event_type=EventTypeEnum.WORLD_STATE_UPDATED,
            source_type=SourceTypeEnum.MCP_TOOL,
            source_name="get_current_hardware_state",
            payload=hardware_state,
            task_id=task_id,
        )

        self.insert_event(environment_event)
        self.insert_event(hardware_event)


        self.world_state = WorldStateSchema(
            session_id=self.session_id,
            environment_state=environment_state,
            hardware_state=hardware_state,
            sources=[], # add sources later, lets just trust it for now or we might remove this later if it is redundant
        )
        return self.world_state

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

    # build teh hardware config later
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

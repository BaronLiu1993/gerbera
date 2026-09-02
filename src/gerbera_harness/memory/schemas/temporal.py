import uuid

from pydantic import Field

from gerbera_harness.memory.schemas.events import EventSchema
from gerbera_harness.memory.schemas.physical import PhysicalConfigurationStateSchema
from gerbera_harness.memory.schemas.task import TaskSchema
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.runtime.schemas.base import HarnessSchema


class TemporalStateSchema(HarnessSchema):
    session_id: str
    recent_events: list[EventSchema] = Field(default_factory=list)
    recent_world_states: list[WorldStateSchema] = Field(default_factory=list)
    recent_physical_configurations: list[
        PhysicalConfigurationStateSchema
    ] = Field(default_factory=list)
    recent_task_results: list[TaskSchema] = Field(default_factory=list)
    task_event_traces: dict[str, list[EventSchema]] = Field(default_factory=dict)
    source_event_traces: dict[str, list[EventSchema]] = Field(default_factory=dict)
    event_type_traces: dict[str, list[EventSchema]] = Field(default_factory=dict)
    temporal_memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

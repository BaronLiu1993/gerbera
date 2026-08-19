import uuid
from typing import Any

from pydantic import Field

from gerbera_harness.memory.schemas.events import EventSchema
from gerbera_harness.memory.schemas.task import TaskSchema, ToolSchema
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.runtime.schemas.base import HarnessSchema


class TemporalStateSchema(HarnessSchema):
    session_id: str
    current_hardware_configuration: dict[str, Any]
    recent_events: list[EventSchema] = Field(default_factory=list)
    recent_world_states: list[WorldStateSchema] = Field(default_factory=list)
    recent_task_results: list[TaskSchema] = Field(default_factory=list)
    temporal_memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

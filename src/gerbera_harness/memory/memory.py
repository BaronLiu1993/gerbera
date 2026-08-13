from dataclasses import dataclass

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

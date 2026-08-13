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
    # The workflow orchestrator should set this to the main agent run_id.
    session_id: str
    user_goal: str
    world_state: WorldStateSchema # Includes environment and the actual hardware state right now of each sensor and motor
    temporal_state: TemporalStateSchema
    task_state: TaskStateSchema
    events_state: EventStateSchema
    hardware_configuration: HardwareConfigurationStateSchema

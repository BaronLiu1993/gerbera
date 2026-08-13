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

    def define_world_state(self) -> WorldStateSchema:
        

        environment_state = 



        hardware_state = {

        }

        self.world_state = WorldStateSchema(
            session_id=self.session_id,
            environment_state=environment_state,
            hardware_state=hardware_state,
            sources=[],
        )

    def get_world_state(self):
        pass

    def define_task_state(self):
        pass

    def get_task_state(self):
        pass

    def define_hardware_configuration(self):
        pass

    def get_hardware_configuration(self):
        return self.hardware_configuration

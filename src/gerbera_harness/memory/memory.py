from dataclasses import dataclass

from gerbera_harness.memory.schemas import (
    EventSchema,
    EventStateSchema,
    EventTypeEnum,
    PhysicalConfigurationStateSchema,
    TaskSchema,
    TaskStateSchema,
    TemporalStateSchema,
    WorldStateSchema,
)


@dataclass
class Memory:
    session_id: str
    world_state: WorldStateSchema
    temporal_state: TemporalStateSchema
    task_state: TaskStateSchema | None
    events_state: EventStateSchema
    physical_configuration: PhysicalConfigurationStateSchema

    def define_world_state(self, world_state: WorldStateSchema) -> None:
        self.world_state = world_state

    def define_initial_physical_configuration(
        self, physical_configuration: PhysicalConfigurationStateSchema
    ) -> None:
        self.physical_configuration = physical_configuration

    def update_hardware_state_by_name(
        self,
        hardware_state_by_name: dict[str, object],
    ) -> None:
        self.physical_configuration.hardware_state_by_name = hardware_state_by_name

    def update_joint_state_by_movement_system(
        self,
        movement_system_name: str,
        joint_state: dict[str, object],
    ) -> None:
        self.physical_configuration.joint_state_by_movement_system[
            movement_system_name
        ] = joint_state

    def require_task_state(self) -> TaskStateSchema:
        if self.task_state is None:
            raise RuntimeError("Task state has not been initialised")
        return self.task_state

    def get_current_task_state(self) -> TaskSchema:
        task_state = self.require_task_state()
        current_task_id = task_state.current_task_id
        for task in task_state.tasks:
            if task.task_id == current_task_id:
                return task
        raise RuntimeError(f"Current task not found: {current_task_id}")

    def get_tasks_state(self) -> TaskStateSchema:
        return self.require_task_state()

    def insert_event(self, event: EventSchema) -> None:
        self.events_state.events.append(event)

    def get_events_state(self) -> list[EventSchema]:
        return list(self.events_state.events)

    def get_events_by_task_id(self, task_id: str) -> list[EventSchema]:
        return list(self.temporal_state.task_event_traces.get(task_id, []))

    def get_current_task_events(self) -> list[EventSchema]:
        task = self.get_current_task_state()
        return self.get_events_by_task_id(task.task_id)

    def get_events_by_source(self, source_name: str) -> list[EventSchema]:
        return list(self.temporal_state.source_event_traces.get(source_name, []))

    def get_events_by_type(
        self,
        event_type: EventTypeEnum,
    ) -> list[EventSchema]:
        return list(self.temporal_state.event_type_traces.get(event_type.value, []))

    def get_temporal_state(self) -> TemporalStateSchema:
        return self.temporal_state

    def rebuild_temporal_state(self, window_size: int = 20) -> None:
        task_state = self.require_task_state()
        events = self.events_state.events
        self.temporal_state.recent_events = events[-window_size:]
        self.temporal_state.recent_task_results = task_state.tasks[-window_size:]
        task_event_traces: dict[str, list[EventSchema]] = {}
        source_event_traces: dict[str, list[EventSchema]] = {}
        event_type_traces: dict[str, list[EventSchema]] = {}
        task_summaries_by_task_id: dict[str, list[dict[str, object]]] = {}

        for event in events:
            task_event_traces.setdefault(event.task_id, []).append(event)
            source_event_traces.setdefault(event.source_name, []).append(event)
            event_type_traces.setdefault(event.event_type.value, []).append(event)
            if event.event_type is EventTypeEnum.REVIEW_CREATED:
                task_summaries_by_task_id.setdefault(event.task_id, []).append(
                    event.payload
                )

        self.temporal_state.task_event_traces = {
            key: value[-window_size:] for key, value in task_event_traces.items()
        }
        self.temporal_state.source_event_traces = {
            key: value[-window_size:] for key, value in source_event_traces.items()
        }
        self.temporal_state.event_type_traces = {
            key: value[-window_size:] for key, value in event_type_traces.items()
        }
        self.temporal_state.task_summaries_by_task_id = {
            key: value[-window_size:]
            for key, value in task_summaries_by_task_id.items()
        }

        # Adding and reconstruct the world states
        self.temporal_state.recent_world_states.append(self.world_state)
        self.temporal_state.recent_world_states = (
            self.temporal_state.recent_world_states[-window_size:]
        )

        self.temporal_state.recent_physical_configurations.append(
            self.physical_configuration.model_copy(deep=True)
        )
        self.temporal_state.recent_physical_configurations = (
            self.temporal_state.recent_physical_configurations[-window_size:]
        )

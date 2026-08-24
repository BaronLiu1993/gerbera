from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.memory.schemas import (
    EventSchema,
    EventStateSchema,
    EventTypeEnum,
    PhysicalConfigurationStateSchema,
    TaskSchema,
    TaskStateSchema,
    TaskStatusEnum,
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
    physical_configuration: PhysicalConfigurationStateSchema | None # temporarily is none

    def define_world_state(self, world_state: WorldStateSchema) -> None:
        self.world_state = world_state

    def define_physical_configuration(self):
        pass
    
    def initialise_tasks(
        self,
        tasks: list[TaskSchema],
        user_intent: str,
        goal: str,
        success_criteria: list[str],
    ) -> None:
        self.task_state = TaskStateSchema(
            user_intent=user_intent,
            goal=goal,
            success_criteria=success_criteria,
            tasks=list(tasks),
            current_task_id=tasks[0].task_id,
        )

    def require_task_state(self) -> TaskStateSchema:
        if self.task_state is None:
            raise RuntimeError("Task state has not been initialised")
        return self.task_state

    def has_remaining_tasks(self) -> bool:
        task_state = self.require_task_state()
        return any(
            task.status is TaskStatusEnum.PENDING
            for task in task_state.tasks
        )

    def advance_to_next_task(self) -> None:
        task_state = self.require_task_state()
        for task in task_state.tasks:
            if task.status is TaskStatusEnum.PENDING:
                task_state.current_task_id = task.task_id
                return

    def complete_task(self) -> None:
        task = self.get_current_task_state()
        if task.status != TaskStatusEnum.IN_PROGRESS:
            raise ValueError("Task has not started yet")
        task.status = TaskStatusEnum.COMPLETED
        task.finished_at = datetime.now(timezone.utc)

    def fail_task(self) -> None:
        task = self.get_current_task_state()
        if task.status != TaskStatusEnum.IN_PROGRESS:
            raise ValueError("Task has not started yet")
        task.status = TaskStatusEnum.FAILED
        task.finished_at = datetime.now(timezone.utc)

    def start_task(self) -> None:
        task_state = self.require_task_state()
        task = self.get_current_task_state()
        task.status = TaskStatusEnum.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        task_state.current_task_id = task.task_id

    # get the one that we are currently working on
    def get_current_task_state(self) -> TaskSchema:
        task_state = self.require_task_state()
        current_task_id = task_state.current_task_id
        for task in task_state.tasks:
            if task.task_id == current_task_id:
                return task
        raise RuntimeError(f"Current task not found: {current_task_id}")

    # get all tasks 
    def get_tasks_state(self) -> TaskStateSchema:
        return self.require_task_state()

    # add an event
    def insert_event(self, event: EventSchema) -> None:
        self.events_state.events.append(event)

    # get all events state
    def get_events_state(self) -> list[EventSchema]:
        return list(self.events_state.events)

    def get_events_by_task_id(self, task_id: str) -> list[EventSchema]:
        return list(
            self.temporal_state.task_event_traces.get(task_id, [])
        )

    def get_current_task_events(self) -> list[EventSchema]:
        task = self.get_current_task_state()
        return self.get_events_by_task_id(task.task_id)

    def get_events_by_source(self, source_name: str) -> list[EventSchema]:
        return list(
            self.temporal_state.source_event_traces.get(source_name, [])
        )

    def get_events_by_type(
        self,
        event_type: EventTypeEnum,
    ) -> list[EventSchema]:
        return list(
            self.temporal_state.event_type_traces.get(event_type.value, [])
        )

    def get_temporal_state(self) -> TemporalStateSchema:
        return self.temporal_state

    # build the hardware config later
    def rebuild_temporal_state(self, window_size: int = 20) -> None:
        # self.temporal_state.current_hardware_configuration =
        task_state = self.require_task_state()
        events = self.events_state.events
        self.temporal_state.recent_events = events[-window_size:]
        self.temporal_state.recent_task_results = task_state.tasks[-window_size:]
        task_event_traces: dict[str, list[EventSchema]] = {}
        source_event_traces: dict[str, list[EventSchema]] = {}
        event_type_traces: dict[str, list[EventSchema]] = {}

        for event in events:
            task_event_traces.setdefault(event.task_id, []).append(event)
            source_event_traces.setdefault(event.source_name, []).append(event)
            event_type_traces.setdefault(event.event_type.value, []).append(event)

        self.temporal_state.task_event_traces = {
            key: value[-window_size:]
            for key, value in task_event_traces.items()
        }
        self.temporal_state.source_event_traces = {
            key: value[-window_size:]
            for key, value in source_event_traces.items()
        }
        self.temporal_state.event_type_traces = {
            key: value[-window_size:]
            for key, value in event_type_traces.items()
        }

        # Adding and reconstruct the world states
        self.temporal_state.recent_world_states.append(self.world_state)
        self.temporal_state.recent_world_states = (
            self.temporal_state.recent_world_states[-window_size:]
        )

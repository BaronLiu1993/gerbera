from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.memory.schemas import (
    EventSchema,
    EventStateSchema,
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
    task_state: TaskStateSchema
    events_state: EventStateSchema
    physical_configuration: PhysicalConfigurationStateSchema

    def define_world_state(self, world_state: WorldStateSchema) -> None:
        self.world_state = world_state

    def initialise_tasks(
        self,
        tasks: list[TaskSchema],
        user_intent: str,
        goal: str,
    ) -> None:
        self.task_state.user_intent = user_intent
        self.task_state.goal = goal
        self.task_state.tasks = list(tasks)
        self.task_state.current_task_id = tasks[0].task_id

    def has_current_task(self) -> bool:
        return any(
            task.task_id == self.task_state.current_task_id
            for task in self.task_state.tasks
        )

    def has_remaining_tasks(self) -> bool:
        return any(
            task.status is TaskStatusEnum.PENDING
            for task in self.task_state.tasks
        )

    def advance_to_next_task(self) -> None:
        for task in self.task_state.tasks:
            if task.status is TaskStatusEnum.PENDING:
                self.task_state.current_task_id = task.task_id
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
        task = self.get_current_task_state()
        task.status = TaskStatusEnum.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        self.task_state.current_task_id = task.task_id

    # get the one that we are currently working on
    def get_current_task_state(self) -> TaskSchema:
        current_task_id = self.task_state.current_task_id
        for task in self.task_state.tasks:
            if task.task_id == current_task_id:
                return task
        raise RuntimeError(f"Current task not found: {current_task_id}")

    # get all tasks 
    def get_tasks_state(self) -> TaskStateSchema:
        return self.task_state

    # add an event
    def insert_event(self, event: EventSchema) -> None:
        self.events_state.events.append(event)

    # get all events state
    def get_events_state(self) -> list[EventSchema]:
        return list(self.events_state.events)

    def get_temporal_state(self) -> TemporalStateSchema:
        return self.temporal_state

    # build the hardware config later
    def rebuild_temporal_state(self, window_size: int = 20) -> None:
        # self.temporal_state.current_hardware_configuration =
        self.temporal_state.recent_events = self.events_state.events[-window_size:]
        self.temporal_state.recent_task_results = self.task_state.tasks[-window_size:]

        # Adding and reconstruct the world states
        self.temporal_state.recent_world_states.append(self.world_state)
        self.temporal_state.recent_world_states = (
            self.temporal_state.recent_world_states[-window_size:]
        )

    #
    # def define_physical_configuration(self):
    #     pass

    # def get_hardware_configuration(self):
    #     return self.physical_configuration

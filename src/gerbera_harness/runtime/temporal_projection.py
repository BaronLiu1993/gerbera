from dataclasses import dataclass

from gerbera_harness.memory import EventSchema, EventTypeEnum, Memory


@dataclass(frozen=True)
class TemporalStateProjection:
    memory: Memory

    def rebuild(self, window_size: int = 20) -> None:
        task_state = self.memory.require_task_state()
        events = self.memory.events_state.events
        self.memory.temporal_state.recent_events = events[-window_size:]
        self.memory.temporal_state.recent_task_results = task_state.tasks[-window_size:]
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

        self.memory.temporal_state.task_event_traces = {
            key: value[-window_size:] for key, value in task_event_traces.items()
        }
        self.memory.temporal_state.source_event_traces = {
            key: value[-window_size:] for key, value in source_event_traces.items()
        }
        self.memory.temporal_state.event_type_traces = {
            key: value[-window_size:] for key, value in event_type_traces.items()
        }
        self.memory.temporal_state.task_summaries_by_task_id = {
            key: value[-window_size:]
            for key, value in task_summaries_by_task_id.items()
        }

        self.memory.temporal_state.recent_world_states.append(self.memory.world_state)
        self.memory.temporal_state.recent_world_states = (
            self.memory.temporal_state.recent_world_states[-window_size:]
        )

        self.memory.temporal_state.recent_physical_configurations.append(
            self.memory.physical_configuration.model_copy(deep=True)
        )
        self.memory.temporal_state.recent_physical_configurations = (
            self.memory.temporal_state.recent_physical_configurations[-window_size:]
        )

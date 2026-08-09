from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.event import Event

# Add an event and, we dispatch a predefined event here
@dataclass
class EventBus:
    events: dict[tuple[str, str, str], Event] = field(default_factory=dict)

    def add_event(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        event: Event,
    ) -> None:
        event_key = (event_type, microcontroller_id, event_name)
        if event_key in self.events:
            raise RuntimeError("Event already exists")

        self.events[event_key] = event

    def get_event(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> Event:
        event_key = (event_type, microcontroller_id, event_name)
        if event_key not in self.events:
            raise RuntimeError("Event does not exist")

        return self.events[event_key]

    # Containing all events, flush every single one of them
    def flush_event_buffers(self) -> None:
        for event in self.events.values():
            if event.streamable:
                event.flush()

from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.event import Event


EventKey = tuple[str, str, str]

@dataclass
class EventBus:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    events: dict[EventKey, Event] = field(default_factory=dict)

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

    def get_handler(self, event_key: EventKey) -> Event:
        if event_key not in self.events:
            raise RuntimeError("Event does not exist")

        return self.events[event_key]

    def flush_stream_buffers(self) -> None:
        for event in self.events.values():
            if event.streamable:
                event.flush()

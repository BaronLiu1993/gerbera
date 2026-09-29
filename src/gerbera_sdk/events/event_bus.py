from dataclasses import dataclass, field

from gerbera_sdk.events.event import Event

EventKey = tuple[str, str, str]


@dataclass
class EventBus:
    events: dict[EventKey, Event] = field(default_factory=dict)

    def write_event(
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

    def flush_event_buffers(self) -> None:
        for event in self.events.values():
            if event.streamable:
                event.flush()

from dataclasses import dataclass, field

from gerbera_sdk.events.event import Event


EventKey = tuple[str, str, str]

@dataclass
class EventBus:
    event_bus_id: str
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

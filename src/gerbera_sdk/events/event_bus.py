from dataclasses import dataclass, field

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_schema import EventKey
from gerbera_sdk.events.event_worker import EventWorker

@dataclass
class EventBus:
    events: dict[EventKey, Event] = field(default_factory=dict)

    def register(self, worker: EventWorker) -> None:
        for board in plan.boards:
            for connection in board.connections:
                self.register_connection(connection, "MCP", worker)
                if connection.stream_enabled:
                    self.register_connection(connection, "STREAM", worker)

    def register_connection(
        self, connection: ResolvedConnection, event_type: str, worker: EventWorker
    ) -> None:
        event_key = EventKey(event_type, connection.microcontroller_id, connection.event_name)
        event = Event(
            event_key=event_key,
            buffer=Buffer(table_name=connection.event_name, event_worker=worker),
        )
        self.write_event(event_type, connection.microcontroller_id, connection.event_name, event)

    def write_event(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        event: Event,
    ) -> None:
        event_key = EventKey(event_type, microcontroller_id, event_name)
        if event_key in self.events:
            raise RuntimeError("Event already exists")

        self.events[event_key] = event

    def get_event(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> Event:
        event_key = EventKey(event_type, microcontroller_id, event_name)
        if event_key not in self.events:
            raise RuntimeError("Event does not exist")

        return self.events[event_key]

    def flush_event_buffers(self) -> None:
        for event in self.events.values():
            if event.streamable:
                event.flush()

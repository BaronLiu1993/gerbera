from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_schema import EventKey
from gerbera_sdk.config.firmware_config import load_firmware_config

if TYPE_CHECKING:
    from gerbera_sdk.events.event_worker import EventWorker
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class EventBus:
    events: dict[EventKey, Event] = field(default_factory=dict)

    def register(self, hardware: "HardwareSystem", worker: "EventWorker") -> None:
        for board in hardware.microcontrollers:
            for connection in board.connections:
                board_id = board.microcontroller_id
                connection_id = connection.connection_id
                config = load_firmware_config(connection.component_type)
                reply_fields = {}
                write = config.get("write")
                if write is not None:
                    response_field = write["response_field"]
                    response_settings = write["params"].get(response_field, {})
                    reply_fields[response_field] = response_settings.get("unit")

                stream = config.get("stream")
                if connection.supports_streaming and stream is not None:
                    reply_fields["stream_enabled"] = None
                    reading_field = stream["field"]
                    self.register_event(Event(
                        event_key=EventKey("STREAM", board_id, connection_id),
                        buffer=Buffer(table_name=connection_id, event_worker=worker),
                        payload_fields={reading_field: stream.get("unit")},
                    ))

                if reply_fields:
                    self.register_event(Event(
                        event_key=EventKey("MCP", board_id, connection_id),
                        payload_fields=reply_fields,
                    ))

    def register_event(self, event: Event) -> None:
        if event.event_key in self.events:
            raise RuntimeError("Event already exists")
        self.events[event.event_key] = event

    def get_event(self, event_type: str, microcontroller_id: str, event_name: str) -> Event:
        key = EventKey(event_type, microcontroller_id, event_name)
        try:
            return self.events[key]
        except KeyError as error:
            raise RuntimeError(f"Event does not exist: {key}") from error

    def flush_event_buffers(self) -> None:
        for event in self.events.values():
            if event.streamable:
                event.flush()

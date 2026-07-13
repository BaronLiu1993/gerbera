from dataclasses import dataclass

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.models.connection import Connection
from gerbera_sdk.models.microcontroller import Microcontroller


@dataclass
class StreamController:
    event_bus: EventBus

    def stop_stream(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        self.flush_stream(microcontroller, connection)
        event_worker.flush_now()

    def flush_stream(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        event = self.event_bus.get_handler(
            ("STREAM", microcontroller.id, connection.event_name)
        )
        event.flush()

    def flush_all(self) -> None:
        self.event_bus.flush_stream_buffers()
        event_worker.flush_now()

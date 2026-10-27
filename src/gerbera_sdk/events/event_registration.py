from dataclasses import dataclass

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedConnection


@dataclass
class EventRegistration:
    plan: HardwarePlan
    bus: EventBus
    worker: EventWorker

    def register(self) -> None:
        for board in self.plan.boards:
            for connection in board.connections:
                self.register_connection(connection, "MCP")
                if connection.stream_enabled:
                    self.register_connection(connection, "STREAM")

    def register_connection(self, connection: ResolvedConnection, event_type: str) -> None:
        event_key = (event_type, connection.microcontroller_id, connection.event_name)
        event = Event(
            event_type=event_type,
            microcontroller_id=connection.microcontroller_id,
            event_name=connection.event_name,
            connection_name=connection.name,
            component_type=connection.component_type,
            streamable=event_type == "STREAM",
            table_name=connection.event_name,
            buffer=Buffer(table_name=connection.event_name, event_worker=self.worker),
            event_key=event_key,
        )
        self.bus.write_event(*event_key, event)

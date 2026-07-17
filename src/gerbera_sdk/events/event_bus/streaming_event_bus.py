from dataclasses import dataclass
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.events.events.stream_event import StreamEvent

# Needs to differ as we register different events
@dataclass
class StreamingEventBus:
    streaming_event_bus_id: str
    hardware_system: HardwareSystem
    event_bus: dict[tuple[str, str], StreamEvent]

    def add_event(self, microcontroller_id: str, event_name: str, event: StreamEvent):
        event_key = (microcontroller_id, event_name)

        if event_key in self.event_bus:
            raise RuntimeError("Event Already Exists")
        self.event_bus[event_key] = event
    
    # event_key is a tuple
    def get_handler(self, event_key):
        if event_key not in self.event_bus:
            raise RuntimeError("Event Does Not Exist")

        return self.event_bus[event_key]

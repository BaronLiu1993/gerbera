from dataclasses import dataclass

from gerbera_sdk.events.event import Event
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem

# Needs to differ as we register different events
@dataclass
class StreamingEventBus:
    streaming_event_bus_id: str
    hardware_system: HardwareSystem
    event_bus: dict[tuple[str, str], Event]

    def add_event(self, microcontroller_id: str, event_name: str, event: Event):
        event_key = (microcontroller_id, event_name)

        if event_key in self.event_bus:
            raise RuntimeError("Event Already Exists")
        self.event_bus[event_key] = event
    
    # event_key is a tuple
    def get_handler(self, event_key):
        if event_key not in self.event_bus:
            raise RuntimeError("Event Does Not Exist")

        return self.event_bus[event_key]

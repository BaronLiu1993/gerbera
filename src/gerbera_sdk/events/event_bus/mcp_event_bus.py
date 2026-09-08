from dataclasses import dataclass

from gerbera_sdk.events.event import Event
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.utils import build_event_key

# Needs to differ as we register different events
@dataclass
class MCPEventBus:
    mcp_event_bus_id: str
    hardware_system: HardwareSystem
    event_bus: dict[str, Event]

    def add_event(self, microcontroller_id: str, event_name: str, event: Event):
        event_key = build_event_key("MCP", microcontroller_id, event_name)

        if event_key in self.event_bus:
            raise RuntimeError("Event Already Exists")

        self.event_bus[event_key] = event
    
    def get_handler(self, event_key: str):
        if event_key not in self.event_bus:
            raise RuntimeError("Event Does Not Exist")

        return self.event_bus[event_key]

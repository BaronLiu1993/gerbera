from dataclasses import dataclass
from event import Event

@dataclass
class EventBus:
    id: str
    hardware_system_id: str
    event_bus: dict[str, ]

    def add_pub_sub(self, event_name: str, event: Event) :
        if event_name in self.event_bus:
            raise RuntimeError("Event Already Exists")
        self.event_bus[event_name] = event
    
    def publish(self, event_name):
        if event_name not in self.event_bus:
            raise RuntimeError("Event Does Not Exist")

        event = self.event_bus[event_name]
        event.execute_side_effect()
        
    


        
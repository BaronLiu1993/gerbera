from dataclasses import dataclass

@dataclass
class MCPEvent:
    event_id: str
    event_bus_id: str
    event_name: str

    def perform_work(self, payload):
        pass

        

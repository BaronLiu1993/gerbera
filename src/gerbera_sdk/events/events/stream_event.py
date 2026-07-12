from abc import abstractmethod
from dataclasses import dataclass

@dataclass
class StreamEvent:
    event_id: str
    event_bus_id: str
    event_name: str
    buffer_name: str

    @abstractmethod
    def perform_work(self, payload):
        raise NotImplementedError

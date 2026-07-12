from dataclasses import dataclass, field


@dataclass
class Event:
    event_id: str
    event_bus_id: str
    event_name: str
    payload: dict[str, str] = field(default_factory=dict)

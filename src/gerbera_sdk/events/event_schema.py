from dataclasses import dataclass


@dataclass(frozen=True)
class EventKey:
    event_type: str
    microcontroller_id: str
    event_name: str

@dataclass(frozen=True)
class WriteJob:
    table_name: str
    batch: list[dict[str, str]]

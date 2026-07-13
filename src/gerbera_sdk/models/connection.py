from dataclasses import dataclass
from typing import Any, Optional
import uuid

from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.models.database import Database
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event import Event


@dataclass
class Connection:
    id: str
    microcontroller_id: str
    name: str
    component_type: str
    pins: Optional[dict[str, str]] = None
    description: str = ""
    database: Database | None = None
    event_bus: EventBus | None = None

    def __post_init__(self) -> None:
        if self.event_bus is None:
            return

        if self.database is not None:
            from gerbera_sdk.firmware.configurations import DEVICES_MAPPING

            event_worker.configure_database(self.database)
            event_worker.start()

            if self.component_type not in DEVICES_MAPPING:
                raise ValueError(
                    f"Unsupported component type for schema generation: "
                    f"{self.component_type}"
                )

            builder = DEVICES_MAPPING[self.component_type]()
            schema = builder.required_schema(self)
            table_name = f"{self.component_type}_{self.id}"
            self.database.create_database_table(table_name, schema)
            self._register_stream_event(table_name)

        self._register_mcp_event()

    def _register_stream_event(self, table_name: str) -> None:
        event_type = "STREAM"
        event_name = f"{self.component_type}_{self.id}"
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            microcontroller_id=self.microcontroller_id,
            event_name=event_name,
            streamable=True,
            table_name=table_name,
        )
        self.event_bus.add_event(
            event_type,
            self.microcontroller_id,
            event_name,
            event,
        )

    def _register_mcp_event(self) -> None:
        event_type = "MCP"
        event_name = f"{self.component_type}_{self.id}"
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            microcontroller_id=self.microcontroller_id,
            event_name=event_name,
        )
        self.event_bus.add_event(
            event_type,
            self.microcontroller_id,
            event_name,
            event,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "component_type": self.component_type,
            "pins": dict(self.pins or {}),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            id=str(payload.get("id", "")),
            microcontroller_id=str(payload.get("microcontroller_id", "")),
            name=str(payload.get("name", "")),
            component_type=str(payload.get("component_type", "")),
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            description=str(payload.get("description", "")),
        )

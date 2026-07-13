from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Optional
import uuid

from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.models.database import Database
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event import Event


@dataclass
class Connection:
    MAX_EVENT_NAME_LENGTH = 63

    name: str
    component_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    microcontroller_id: str = ""
    hardware_system_id: str = ""
    pins: Optional[dict[str, str]] = None
    description: str = ""
    database: Database | None = None
    event_bus: EventBus | None = None

    @property
    def event_name(self) -> str:
        connection_key = self.id or self.name
        connection_hash = hashlib.sha1(connection_key.encode()).hexdigest()[:8]
        if self.microcontroller_id:
            microcontroller_hash = hashlib.sha1(
                self.microcontroller_id.encode()
            ).hexdigest()[:8]
            return self._safe_identifier(
                f"{self.component_type}_{microcontroller_hash}_{connection_hash}"
            )

        return self._safe_identifier(f"{self.component_type}_{connection_hash}")

    @classmethod
    def _safe_identifier(cls, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
        if len(normalized) <= cls.MAX_EVENT_NAME_LENGTH:
            return normalized

        digest = hashlib.sha1(normalized.encode()).hexdigest()[:8]
        prefix_length = cls.MAX_EVENT_NAME_LENGTH - len(digest) - 1
        return f"{normalized[:prefix_length].rstrip('_')}_{digest}"

    def __post_init__(self) -> None:
        if self.event_bus is None:
            return

        from gerbera_sdk.firmware.configurations import DEVICES_MAPPING

        if self.component_type not in DEVICES_MAPPING:
            raise ValueError(
                f"Unsupported component type for event registration: "
                f"{self.component_type}"
            )

        builder = DEVICES_MAPPING[self.component_type]()

        if self.database is not None:
            if not builder.supports_database:
                raise ValueError(
                    f"{self.component_type} does not support database streaming"
                )

            event_worker.configure_database(self.database)
            event_worker.start()

            schema = builder.required_schema(self)
            table_name = self.event_name
            self.database.create_database_table(table_name, schema)
            self._register_stream_event(table_name)

        self._register_mcp_event()

    def _register_stream_event(self, table_name: str) -> None:
        event_type = "STREAM"
        event_name = self.event_name
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
        event_name = self.event_name
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
            "hardware_system_id": self.hardware_system_id,
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "component_type": self.component_type,
            "pins": dict(self.pins or {}),
            "database": self.database.to_dict() if self.database is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            id=str(payload.get("id", "")),
            hardware_system_id=str(payload.get("hardware_system_id", "")),
            microcontroller_id=str(payload.get("microcontroller_id", "")),
            name=str(payload.get("name", "")),
            component_type=str(payload.get("component_type", "")),
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            description=str(payload.get("description", "")),
            database=(
                Database.from_dict(payload["database"])
                if payload.get("database") is not None
                else None
            ),
        )

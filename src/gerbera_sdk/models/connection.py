from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import uuid

from gerbera_sdk.contracts.firmware_contract import OutputEventType
from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.models.database import Database
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.utils import build_connection_event_name


@dataclass
class Connection:
    name: str
    component_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    microcontroller_id: str = ""
    hardware_system_id: str = ""
    pins: Optional[dict[str, str]] = None
    description: str = ""
    database: Database | None = None
    event_bus: EventBus | None = None
    actions: dict[
        str,
        Callable[[Optional[dict[str, str]]], dict[str, str]],
    ] = field(default_factory=dict, repr=False)

    @property
    def event_name(self) -> str:
        return build_connection_event_name(
            component_type=self.component_type,
            microcontroller_id=self.microcontroller_id,
            pins=self.pins,
        )

    def __post_init__(self) -> None:
        if self.event_bus is None:
            return

        builder = self._get_builder()

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
        builder = self._get_builder()

        event = Event(
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

    def register_action(
        self,
        action: str,
        callback: Callable[[Optional[dict[str, str]]], dict[str, str]],
    ) -> None:
        self.actions[action.strip().upper()] = callback

    def perform_action(
        self,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        normalized_action = action.strip().upper()
        if normalized_action not in self.actions:
            raise RuntimeError(
                f"Action is not registered for {self.name}: {normalized_action}"
            )

        return self.actions[normalized_action](params)

    def _get_builder(self):
        from gerbera_sdk.firmware.configurations import DEVICES_MAPPING

        if self.component_type not in DEVICES_MAPPING:
            raise ValueError(
                f"Unsupported component type for event registration: "
                f"{self.component_type}"
            )

        return DEVICES_MAPPING[self.component_type]()
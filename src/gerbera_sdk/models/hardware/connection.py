from dataclasses import dataclass, field
from typing import Callable, Optional

from pin import Pin
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.utils import build_connection_event_name


@dataclass
class Connection:
    name: str
    component_type: str
    microcontroller_id: str = ""
    pins: dict[Pin, str]
    description: str = ""
    database: Optional[Database] # we define it here, we check at runtime if this component has a database even
    # event_bus: EventBus | None = None, we define an event bus elsewhere, we register it at runtime
    # actions: dict[
    #     str,
    #     Callable[[Optional[dict[str, str]]], dict[str, str]],
    # ] = field(default_factory=dict, repr=False)

    # We need this to create the event name that the postgres table uses for streaming
    # and it is what events use as a unique identifier
    @property
    def event_name(self) -> str:
        return build_connection_event_name(
            component_type=self.component_type,
            microcontroller_id=self.microcontroller_id,
            pins=self.pins,
        )

    # def __post_init__(self) -> None:
    #     builder = self._get_builder()

    #     if self.database is not None:
    #         if not builder.supports_database:
    #             raise ValueError(
    #                 f"{self.component_type} does not support database streaming"
    #             )

    #         #event_worker.configure_database(self.database)
    #         #event_worker.start() Should not do this, it should be taken by runtime

    #         schema = builder.required_schema(self)
    #         self.database.create_database_table(self.event_name, schema)
    #         self._register_stream_event(self.event_name)

    #     self._register_mcp_event()
    
    # def _get_builder(self):

    #     if self.component_type not in DEVICES_MAPPING:
    #         raise ValueError(
    #             f"Unsupported component type for event registration: "
    #             f"{self.component_type}"
    #         )

    #     return DEVICES_MAPPING[self.component_type]()

    # def _register_stream_event(self, table_name: str) -> None:
    #     event_type = "STREAM"
    #     event_name = self.event_name

    #     event = Event(
    #         event_type=event_type,
    #         microcontroller_id=self.microcontroller_id,
    #         event_name=event_name,
    #         streamable=True,
    #         table_name=table_name,
    #     )
    #     self.event_bus.add_event(
    #         event_type,
    #         self.microcontroller_id,
    #         event_name,
    #         event,
    #     )

    # def _register_mcp_event(self) -> None:
    #     event_type = "MCP"
    #     event_name = self.event_name

    #     event = Event(
    #         event_type=event_type,
    #         microcontroller_id=self.microcontroller_id,
    #         event_name=event_name,
    #     )

    #     self.event_bus.add_event(
    #         event_type,
    #         self.microcontroller_id,
    #         event_name,
    #         event,
    #     )

    # def register_action(
    #     self,
    #     action: str,
    #     callback: Callable[[Optional[dict[str, str]]], dict[str, str]],
    # ) -> None:
    #     self.actions[action.strip().upper()] = callback

    # def perform_action(
    #     self,
    #     action: str,
    #     params: Optional[dict[str, str]] = None,
    # ) -> dict[str, str]:
    #     normalized_action = action.strip().upper
    #     if normalized_action not in self.actions:
    #         raise RuntimeError(
    #             f"Action is not registered for {self.name}: {normalized_action}"
    #         )

    #     return self.actions[normalized_action](params)

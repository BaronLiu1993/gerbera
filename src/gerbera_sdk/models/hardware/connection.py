from dataclasses import dataclass
from typing import Optional

from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.pin import Pin
from gerbera_sdk.utils import build_connection_event_name


@dataclass
class Connection:
    name: str
    component_type: str
    pins: dict[Pin, str]
    microcontroller_id: str = ""
    description: str = ""
    database: Optional[Database] = None
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

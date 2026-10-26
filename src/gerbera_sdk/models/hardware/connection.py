from dataclasses import field
from typing import Annotated, Callable

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

from gerbera_sdk.utils import build_connection_event_name


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Connection:
    name: Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
    component_type: Annotated[str, Field(min_length=1, pattern=r"\S")]
    pins: dict[Annotated[str, Field(min_length=1, pattern=r"\S")], Annotated[str, Field(min_length=1, pattern=r"\S")]]
    description: str
    microcontroller_id: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None
    stream: bool = False
    actions: dict[
        str,
        Callable[[dict[str, object]], dict[str, object]],
    ] = field(default_factory=dict, repr=False)

    @property
    def stream_enabled(self) -> bool:
        return self.stream

    @property
    def event_name(self) -> str:
        if self.microcontroller_id is None:
            raise RuntimeError(
                f"Connection is not bound to a microcontroller: {self.name}"
            )

        return build_connection_event_name(
            microcontroller_id=self.microcontroller_id,
            connection_name=self.name,
        )

    def register_action(
        self,
        action: str,
        callback: Callable[[dict[str, object]], dict[str, object]],
    ) -> None:
        self.actions[action.strip().upper()] = callback

    def perform_action(
        self,
        action: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        normalized_action = action.strip().upper()
        if normalized_action not in self.actions:
            raise RuntimeError(
                f"Action is not registered for {self.name}: {normalized_action}"
            )

        return self.actions[normalized_action](params)

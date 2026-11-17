from dataclasses import dataclass
from typing import ClassVar

from gerbera_sdk.utils import build_connection_event_name


@dataclass(kw_only=True)
class Connection:
    name: str
    description: str = ""
    microcontroller_id: str | None = None
    stream: bool = False
    component_type: ClassVar[str]

    @property
    def pins(self) -> dict[str, str]:
        raise NotImplementedError

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

from dataclasses import dataclass, field
from typing import List

from gerbera_sdk.classes.connections import Connection


@dataclass
class Microcontroller:
    id: str
    port: str
    transport: str
    baud_rate: int
    connections: List[Connection] = field(default_factory=list)

    def add_connection(self, connection: Connection) -> bool:
        used_pins = self._get_used_pins()

        for pin in connection.pins:
            if pin in used_pins:
                return False

        self.connections.append(connection)
        return True

    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins:
                used_pins.add(pin)

        return used_pins

from dataclasses import dataclass
from typing import Any
import json
from pathlib import Path

from gerbera_sdk.hardware.connections import Connection

DEVICE_REGISTRY_PATH = Path("devices.json")

@dataclass
class Microcontroller:
    """A microcontroller board and the components connected to it."""
    id: str
    description: str

    def add_connection(self, connection: Connection) -> bool:
        """Add a connection if none of its pins are already in use."""
        port, transport, baud_rate, connections = 
        used_pins = self._get_used_pins()

        for pin in connection.pins:
            if pin.pin_val in used_pins:
                return False

        self.connections.append(connection)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "port": self.port,
            "transport": self.transport,
            "baud_rate": self.baud_rate,
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Microcontroller":
        return cls(
            id=payload["id"],
            port=payload["port"],
            transport=payload["transport"],
            baud_rate=int(payload["baud_rate"]),
            connections=[
                Connection.from_dict(connection)
                for connection in payload.get("connections", [])
            ],
        )


    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins:
                used_pins.add(pin.pin_val)

        return used_pins

    def _get_board_information(self) -> dict[]:
        payload = json.loads(DEVICE_REGISTRY_PATH.read_text())
        device = payload[self.id]
        port, transport, baud_rate, connections = device["port"], device["baud_rate"], device[""]

        return ()


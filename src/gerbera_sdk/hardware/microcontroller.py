from dataclasses import dataclass, field
from typing import Any
import json
from pathlib import Path

from gerbera_sdk.hardware.connections import Connection

DEVICE_REGISTRY_PATH = Path("devices.json")


@dataclass
class Microcontroller:
    """A microcontroller board and the components connected to it."""

    id: str
    description: str = ""
    connections: list[Connection] = field(default_factory=list)

    def add_connection(self, connection: Connection) -> bool:
        """Add a connection if none of its pins are already in use."""
        self._get_board_information()
        used_pins = self._get_used_pins()

        for pin in connection.pins:
            if pin in used_pins:
                return False

        self.connections.append(connection)
        return True

    def to_dict(self) -> dict[str, Any]:
        board_information = self._get_board_information()

        return {
            "id": self.id,
            "description": self.description,
            "port": board_information["port"],
            "protocol": board_information["protocol"],
            "protocol_label": board_information["protocol_label"],
            "baud_rate": board_information["baud_rate"],
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Microcontroller":
        return cls(
            id=payload["id"],
            description=payload.get("description", ""),
            connections=[Connection.from_dict(connection) for connection in payload.get("connections", [])],
        )

    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins:
                used_pins.add(pin)

        return used_pins

    def _get_board_information(self) -> dict[str, Any]:
        payload = json.loads(DEVICE_REGISTRY_PATH.read_text())
        if self.id not in payload:
            raise ValueError(f"Unknown device id: {self.id}")

        device = payload[self.id]
        return {
            "port": device.get("port", device.get("device", "")),
            "protocol": device.get("protocol", ""),
            "protocol_label": device.get("protocol_label", ""),
            "baud_rate": int(device["baud_rate"]),
        }

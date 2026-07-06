from dataclasses import dataclass, field
from typing import Any
import json
from pathlib import Path

from gerbera_sdk.components.registry import ComponentRegistry
from gerbera_sdk.firmware.generator import FirmwareGenerator
from gerbera_sdk.hardware.connections import Connection
from gerbera_sdk.transport.runtime import ConnectionRuntime

DEVICE_REGISTRY_PATH = Path("devices.json")


@dataclass
class Microcontroller:
    """A microcontroller board and the components connected to it."""

    id: str
    description: str = ""
    baud_rate: int = 115200
    connections: list[Connection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        board_information = self.get_board_information()

        return {
            "id": self.id,
            "description": self.description,
            "port": board_information["port"],
            "protocol": board_information["protocol"],
            "protocol_label": board_information["protocol_label"],
            "baud_rate": self.baud_rate,
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Microcontroller":
        return cls(
            id=payload["id"],
            description=payload.get("description", ""),
            baud_rate=int(payload.get("baud_rate", 115200)),
            connections=[Connection.from_dict(connection) for connection in payload.get("connections", [])],
        )

    def add_connection(self, connection: Connection) -> bool:
        """Add a connection if its command name and pins are not already in use."""
        self.get_board_information()
        ComponentRegistry.validate_pins(connection.component_type, connection.pins)
        if connection.name in self._get_connection_names():
            return False

        used_pins = self._get_used_pins()

        for pin in connection.pins.values():
            if pin in used_pins:
                return False

        self.connections.append(connection)
        return True

    

    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins.values():
                used_pins.add(pin)

        return used_pins

    def _get_connection_names(self) -> set[str]:
        return {connection.name for connection in self.connections}

    def get_board_information(self) -> dict[str, Any]:
        payload = json.loads(DEVICE_REGISTRY_PATH.read_text())
        if self.id not in payload:
            raise ValueError(f"Unknown device id: {self.id}")

        device = payload[self.id]
        return {
            "port": device.get("port", device.get("device", "")),
            "protocol": device.get("protocol", ""),
            "protocol_label": device.get("protocol_label", ""),
        }

    def get_connection(self, connection_name: str) -> Connection:
        for connection in self.connections:
            if connection.name == connection_name:
                return connection

        raise ValueError(f"Unknown connection name for board {self.id}: {connection_name}")

    def build_read_command(self, connection_name: str) -> str:
        return ConnectionRuntime.build_read_command(
            self.get_connection(connection_name)
        )

    def generate_firmware(self) -> str:
        return FirmwareGenerator.generate(self)

    def read(self, connection_name: str) -> dict[str, Any]:
        return ConnectionRuntime.read_with_baud(
            self.get_connection(connection_name),
            self.baud_rate,
        )

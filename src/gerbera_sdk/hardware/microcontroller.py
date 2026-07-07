from dataclasses import dataclass, field
from typing import Any

from gerbera_sdk.components.registry import ComponentRegistry
from gerbera_sdk.hardware.connection import Connection


@dataclass
class Microcontroller:
    id: str
    port: str
    description: str = ""
    baud_rate: int
    protocol: str
    protocol_label: str
    connections: list[Connection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "port": self.port,
            "description": self.description,
            "protocol": self.protocol,
            "protocol_label": self.protocol_label,
            "baud_rate": self.baud_rate,
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Microcontroller":
        return cls(
            id=str(payload["id"]),
            port=str(payload["port"]),
            description=str(payload.get("description", "")),
            baud_rate=int(payload.get("baud_rate", 115200)),
            protocol=str(payload.get("protocol", "serial")),
            protocol_label=str(payload.get("protocol_label", "Serial")),
            connections=[
                Connection.from_dict(connection)
                for connection in payload.get("connections", [])
            ],
        )

    def add_connections(
        self,
        connections: list[Connection],
    ) -> None:
        pending_connections = list(connections)

        for connection in pending_connections:
            ComponentRegistry.validate_pins(connection.component_type, connection.pins)

            if connection.name in self._get_connection_names():
                raise ValueError(
                    f"Connection name already exists on board {self.id}: "
                    f"{connection.name}"
                )

            used_pins = self._get_used_pins()
            for pin in connection.pins.values():
                if pin in used_pins:
                    raise ValueError(
                        f"Pin already in use on board {self.id}: {pin}"
                    )

            self.connections.append(connection)

    def get_connection(self, connection_name: str) -> Connection:
        for connection in self.connections:
            if connection.name == connection_name:
                return connection

        raise ValueError(f"Unknown connection name for board {self.id}: {connection_name}")


    # Helper Functions for Deduping
    def _get_used_pins(self) -> set[str]:
        used_pins: set[str] = set()

        for existing_connection in self.connections:
            for pin in existing_connection.pins.values():
                used_pins.add(pin)

        return used_pins

    def _get_connection_names(self) -> set[str]:
        return {connection.name for connection in self.connections}

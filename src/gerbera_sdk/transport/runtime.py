from typing import Any, Optional

from gerbera_sdk.hardware.connections import Connection
from gerbera_sdk.hardware.microcontroller import Microcontroller
from gerbera_sdk.transport.serial_connection import SerialConnection


class ConnectionRuntime:
    @staticmethod
    def build_command(
        connection: Connection,
        params: Optional[dict[str, tuple[str, Any]]] = None,
    ) -> str:
        if not params:
            return connection.name

        serialized_params = [
            f"{param_name}:{param_type}:{param_value}"
            for param_name, (param_type, param_value) in params.items()
        ]
        return ",".join([connection.name, *serialized_params])

    @staticmethod
    def build_read_command(connection: Connection) -> str:
        return ConnectionRuntime.build_command(connection)

    @staticmethod
    def parse_response(response: str) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        for token in response.split(","):
            if ":" not in token:
                continue

            key, value = token.split(":", 1)
            payload[key] = ConnectionRuntime._coerce_value(value)

        return payload

    @staticmethod
    def read(connection: Connection) -> dict[str, Any]:
        board = Microcontroller(id=connection.microcontroller_id).get_board_information()
        serial_connection = SerialConnection()

        try:
            serial_connection.connect(
                port=board["port"],
                baud=board["baud_rate"],
            )
            response = serial_connection.send(
                ConnectionRuntime.build_read_command(connection)
            )
        finally:
            serial_connection.destroy()

        return ConnectionRuntime.parse_response(response)

    @staticmethod
    def _coerce_value(value: str) -> Any:
        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            return value

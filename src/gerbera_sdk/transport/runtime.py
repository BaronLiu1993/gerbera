from typing import Any, Optional

from gerbera_sdk.hardware.connection import Connection


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
            payload[key] = float(value)

        return payload

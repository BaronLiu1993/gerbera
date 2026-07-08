from typing import Optional

from gerbera_sdk.firmware.function.configurations import DEVICES_MAPPING
from gerbera_sdk.models.connection import Connection


class CommandCompiler:
    @staticmethod
    def _get_builder(connection: Connection):
        if connection.component_type not in DEVICES_MAPPING:
            raise ValueError(
                f"Unsupported component type for command generation: "
                f"{connection.component_type}"
            )

        builder_class = DEVICES_MAPPING[connection.component_type]
        if builder_class is None:
            raise ValueError(
                f"Missing builder for component type: {connection.component_type}"
            )

        return builder_class()

    @staticmethod
    def supported_commands(connection: Connection) -> list[str]:
        builder = CommandCompiler._get_builder(connection)
        if not hasattr(builder, "required_commands"):
            return [f"READ,{connection.name}"]

        return list(builder.required_commands(connection))

    @staticmethod
    def build_command(
        connection: Connection,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> str:
        normalized_action = action.strip().upper()

        for command in CommandCompiler.supported_commands(connection):
            normalized_command = command.strip()
            if not normalized_command.upper().startswith(f"{normalized_action},"):
                continue

            if not params:
                return normalized_command

            serialized_params = [
                f"{key}:{value}"
                for key, value in params.items()
            ]
            return ",".join([normalized_command, *serialized_params])

        if not params:
            return f"{normalized_action},{connection.name}"

        serialized_params = [
            f"{key}:{value}"
            for key, value in params.items()
        ]
        return ",".join([f"{normalized_action},{connection.name}", *serialized_params])

    @staticmethod
    def parse_response(response: str) -> dict[str, str]:
        payload: dict[str, str] = {}

        for token in response.split(","):
            normalized_token = token.strip()
            if ":" not in normalized_token:
                continue

            key, value = normalized_token.split(":", 1)
            payload[key.strip()] = value.strip()

        return payload

from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.firmware_schema import CommandSpec
from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.models.hardware.connection import Connection


class CommandCompiler:
    @staticmethod
    def command_specs(connection: Connection) -> list[CommandSpec]:
        builder = get_device_builder(connection.component_type)
        return list(builder.required_commands(connection))

    @staticmethod
    def command_annotations(
        connection: Connection,
        command: CommandSpec,
    ) -> ToolAnnotations:
        builder = get_device_builder(connection.component_type)
        return builder.annotations(connection, command)

    @staticmethod
    def state_unit(
        component_type: str,
        field_name: str,
    ) -> str | None:
        builder = get_device_builder(component_type)
        units = builder.state_definitions()["units"]
        if field_name not in units:
            raise ValueError(
                f"Unsupported state field for {component_type}: {field_name}"
            )
        return units[field_name]

    @staticmethod
    def state_field(
        component_type: str,
        field_name: str,
    ) -> str:
        CommandCompiler.state_unit(component_type, field_name)
        return field_name

    @staticmethod
    def state_key(
        component_type: str,
        connection_name: str,
        field_name: str,
    ) -> str:
        CommandCompiler.state_unit(component_type, field_name)
        return f"{component_type}.{connection_name}.{field_name}"

    @staticmethod
    def state_keys(connection: Connection) -> list[str]:
        builder = get_device_builder(connection.component_type)
        fields = builder.state_definitions()["units"]
        return [
            CommandCompiler.state_key(
                connection.component_type,
                connection.name,
                field_name,
            )
            for field_name in fields
            if field_name != "stream_enabled" or connection.stream_enabled
        ]

    @staticmethod
    def _command_spec_for_action(
        connection: Connection,
        action: str,
    ) -> CommandSpec:
        normalized_action = action.strip().upper()

        for spec in CommandCompiler.command_specs(connection):
            if spec.method.strip().upper() == normalized_action:
                return spec

        raise ValueError(
            f"Unsupported command for {connection.name}: {normalized_action}"
        )

    @staticmethod
    def build_command(
        connection: Connection,
        action: str,
        params: dict[str, object],
    ) -> str:
        normalized_action = action.strip().upper()
        command_spec = CommandCompiler._command_spec_for_action(
            connection,
            normalized_action,
        )

        if params is None:
            raise ValueError(
                f"Command parameters are required for {normalized_action},{connection.name}"
            )

        command = f"{normalized_action},{connection.name}"
        if not command_spec.params:
            if params:
                for key in params:
                    raise ValueError(
                        f"Unsupported parameter for {normalized_action},{connection.name}: {key}"
                    )
            return command

        parts = [command]

        for key in params:
            if key not in command_spec.params:
                raise ValueError(
                    f"Unsupported parameter for {normalized_action},{connection.name}: {key}"
                )

        for key, param_spec in command_spec.params.items():
            if key not in params:
                if param_spec.required:
                    raise ValueError(
                        f"Missing required parameter for {normalized_action},{connection.name}: {key}"
                    )
                continue

            value = params[key]
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid numeric value for {key} on "
                    f"{normalized_action},{connection.name}: {value}"
                ) from exc

            if param_spec.min is not None and numeric_value < param_spec.min:
                raise ValueError(
                    f"Value for {key} on {normalized_action},{connection.name} "
                    f"must be >= {param_spec.min}"
                )

            if param_spec.max is not None and numeric_value > param_spec.max:
                raise ValueError(
                    f"Value for {key} on {normalized_action},{connection.name} "
                    f"must be <= {param_spec.max}"
                )

            parts.append(f"{key}:{numeric_value}")

        return ",".join(parts)

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

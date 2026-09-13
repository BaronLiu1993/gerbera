from mcp.types import ToolAnnotations

import math

from gerbera_sdk.firmware.firmware_schema import CommandSpec, ParameterSpec
from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.models.hardware.connection import Connection


class CommandCompiler:
    # for movement types only
    SERVO_COMPONENT_TYPES = {"sg90", "mg996r"}

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
    def state_value(
        component_type: str,
        field_name: str,
        value: str,
    ) -> str:
        if CommandCompiler.is_servo_angle(component_type, field_name):
            return str(math.radians(float(value)))

        return value

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
    def normalize_action(action: str) -> str:
        return action.strip().upper()

    @staticmethod
    def command_label(
        action: str,
        connection: Connection,
    ) -> str:
        return f"{action},{connection.name}"

    @staticmethod
    def command_spec_for_action(
        connection: Connection,
        action: str,
    ) -> CommandSpec:
        normalized_action = CommandCompiler.normalize_action(action)

        for spec in CommandCompiler.command_specs(connection):
            if CommandCompiler.normalize_action(spec.method) == normalized_action:
                return spec

        raise ValueError(
            f"Unsupported command for {connection.name}: {normalized_action}"
        )

    @staticmethod
    def require_command_params(
        params: dict[str, object] | None,
        label: str,
    ) -> dict[str, object]:
        if params is None:
            raise ValueError(f"Command parameters are required for {label}")
        return params

    @staticmethod
    def reject_unsupported_params(
        params: dict[str, object],
        param_specs: dict[str, ParameterSpec],
        label: str,
    ) -> None:
        for key in params:
            if key not in param_specs:
                raise ValueError(
                    f"Unsupported parameter for {label}: {key}"
                )

    @staticmethod
    def validate_required_param(
        key: str,
        param_spec: ParameterSpec,
        params: dict[str, object],
        label: str,
    ) -> bool:
        if key in params:
            return True
        if param_spec.required:
            raise ValueError(f"Missing required parameter for {label}: {key}")
        return False

    @staticmethod
    def numeric_param_value(
        key: str,
        value: object,
        label: str,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid numeric value for {key} on {label}: {value}"
            ) from exc

    @staticmethod
    def validate_param_bounds(
        key: str,
        value: float,
        param_spec: ParameterSpec,
        label: str,
    ) -> None:
        if param_spec.min is not None and value < param_spec.min:
            raise ValueError(
                f"Value for {key} on {label} must be >= {param_spec.min}"
            )

        if param_spec.max is not None and value > param_spec.max:
            raise ValueError(
                f"Value for {key} on {label} must be <= {param_spec.max}"
            )

    @staticmethod
    def command_param_parts(
        connection: Connection,
        action: str,
        params: dict[str, object],
        param_specs: dict[str, ParameterSpec],
        label: str,
    ) -> list[str]:
        CommandCompiler.reject_unsupported_params(
            params,
            param_specs,
            label,
        )

        parts: list[str] = []
        for key, param_spec in param_specs.items():
            if not CommandCompiler.validate_required_param(
                key,
                param_spec,
                params,
                label,
            ):
                continue

            numeric_value = CommandCompiler.numeric_param_value(
                key,
                params[key],
                label,
            )
            CommandCompiler.validate_param_bounds(
                key,
                numeric_value,
                param_spec,
                label,
            )
            command_value = CommandCompiler.command_parameter_value(
                connection,
                action,
                key,
                numeric_value,
            )
            parts.append(f"{key}:{command_value}")

        return parts

    @staticmethod
    def build_command(
        connection: Connection,
        action: str,
        params: dict[str, object],
    ) -> str:
        normalized_action = CommandCompiler.normalize_action(action)
        command_spec = CommandCompiler.command_spec_for_action(
            connection,
            normalized_action,
        )
        label = CommandCompiler.command_label(normalized_action, connection)
        command_params = CommandCompiler.require_command_params(params, label)
        parts = [label]

        if command_spec.params:
            parts.extend(
                CommandCompiler.command_param_parts(
                    connection,
                    normalized_action,
                    command_params,
                    command_spec.params,
                    label,
                )
            )
        else:
            CommandCompiler.reject_unsupported_params(
                command_params,
                command_spec.params,
                label,
            )

        return ",".join(parts)

    @staticmethod
    def is_servo_angle(
        component_type: str,
        field_name: str,
    ) -> bool:
        return (
            component_type in CommandCompiler.SERVO_COMPONENT_TYPES
            and field_name == "angle"
        )

    @staticmethod
    def is_servo_angle_write(
        connection: Connection,
        action: str,
        key: str,
    ) -> bool:
        return (
            CommandCompiler.is_servo_angle(connection.component_type, key)
            and action == "WRITE"
        )

    @staticmethod
    def command_parameter_value(
        connection: Connection,
        action: str,
        key: str,
        value: float,
    ) -> float:
        if CommandCompiler.is_servo_angle_write(
            connection,
            action,
            key,
        ):
            return math.degrees(value)

        return value

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

from typing import Optional

from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec, ParameterType
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.models.hardware.connection import Connection


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
    def command_specs(connection: Connection) -> list[CommandSpec]:
        builder = CommandCompiler._get_builder(connection)
        return list(builder.required_commands(connection))

    @staticmethod
    def supported_commands(connection: Connection) -> list[str]:
        return [
            f"{spec.method.strip().upper()},{connection.name}"
            for spec in CommandCompiler.command_specs(connection)
        ]

    @staticmethod
    def spec_for_action(connection: Connection, action: str) -> CommandSpec:
        normalized_action = action.strip().upper()

        for spec in CommandCompiler.command_specs(connection):
            if spec.method.strip().upper() == normalized_action:
                return spec

        return CommandSpec(method=normalized_action)

    @staticmethod
    def _coerce_parameter_value(
        connection: Connection,
        action: str,
        key: str,
        value: str,
        param_spec: ParameterSpec,
    ) -> str:
        if param_spec.type == ParameterType.STRING:
            serialized_value = value
        elif param_spec.type == ParameterType.INT:
            try:
                coerced_value = int(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid int value for {key} on {action},{connection.name}: {value}"
                ) from exc
            serialized_value = str(coerced_value)
            if param_spec.min is not None and coerced_value < param_spec.min:
                raise ValueError(
                    f"Value for {key} on {action},{connection.name} must be >= {param_spec.min}"
                )
            if param_spec.max is not None and coerced_value > param_spec.max:
                raise ValueError(
                    f"Value for {key} on {action},{connection.name} must be <= {param_spec.max}"
                )
        elif param_spec.type == ParameterType.FLOAT:
            try:
                coerced_value = float(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid float value for {key} on {action},{connection.name}: {value}"
                ) from exc
            serialized_value = str(coerced_value)
            if param_spec.min is not None and coerced_value < param_spec.min:
                raise ValueError(
                    f"Value for {key} on {action},{connection.name} must be >= {param_spec.min}"
                )
            if param_spec.max is not None and coerced_value > param_spec.max:
                raise ValueError(
                    f"Value for {key} on {action},{connection.name} must be <= {param_spec.max}"
                )
        elif param_spec.type == ParameterType.BOOL:
            lowered_value = value.strip().lower()
            if lowered_value not in {"true", "false", "1", "0"}:
                raise ValueError(
                    f"Invalid bool value for {key} on {action},{connection.name}: {value}"
                )
            serialized_value = "true" if lowered_value in {"true", "1"} else "false"
        else:
            raise ValueError(f"Unsupported parameter type: {param_spec.type}")

        if param_spec.enum and serialized_value not in param_spec.enum:
            raise ValueError(
                f"Unsupported value for {key} on {action},{connection.name}: {serialized_value}"
            )

        return serialized_value

    @staticmethod
    def build_command(
        connection: Connection,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> str:
        normalized_action = action.strip().upper()
        command_spec = CommandCompiler.spec_for_action(connection, normalized_action)
        allowed_params = command_spec.params

        serialized_args: list[str] = []
        if params:
            for key, value in params.items():
                normalized_key = str(key)
                normalized_value = str(value)

                if allowed_params and normalized_key not in allowed_params:
                    raise ValueError(
                        f"Unsupported parameter for {normalized_action},{connection.name}: "
                        f"{normalized_key}"
                    )

                if normalized_key not in allowed_params:
                    serialized_args.append(f"{normalized_key}:{normalized_value}")
                    continue

                serialized_value = CommandCompiler._coerce_parameter_value(
                    connection=connection,
                    action=normalized_action,
                    key=normalized_key,
                    value=normalized_value,
                    param_spec=allowed_params[normalized_key],
                )
                serialized_args.append(f"{normalized_key}:{serialized_value}")

        missing_required_params = [
            key for key, spec in allowed_params.items() if spec.required and (not params or key not in params)
        ]
        if missing_required_params:
            raise ValueError(
                f"Missing required parameter for {normalized_action},{connection.name}: "
                f"{', '.join(missing_required_params)}"
            )

        for command in CommandCompiler.supported_commands(connection):
            normalized_command = command.strip()
            if not normalized_command.upper().startswith(f"{normalized_action},"):
                continue

            if not serialized_args:
                return normalized_command

            return ",".join([normalized_command, *serialized_args])

        if not serialized_args:
            return f"{normalized_action},{connection.name}"

        return ",".join([f"{normalized_action},{connection.name}", *serialized_args])

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

    @staticmethod
    def describe_command(connection: Connection, action: str) -> str:
        command_spec = CommandCompiler.spec_for_action(connection, action)
        allowed_params = command_spec.params

        if not allowed_params:
            return f"{action.strip().upper()},{connection.name}"

        param_descriptions = [
            (
                f"{key} ({metadata.type.value})"
                + (" required" if metadata.required else " optional")
                + (
                    f': {", ".join(metadata.enum)}'
                    if metadata.enum
                    else ""
                )
                + (
                    f" min={metadata.min}"
                    if metadata.min is not None
                    else ""
                )
                + (
                    f" max={metadata.max}"
                    if metadata.max is not None
                    else ""
                )
                + (
                    f" - {metadata.description}"
                    if metadata.description
                    else ""
                )
            )
            for key, metadata in allowed_params.items()
        ]
        return (
            f'{action.strip().upper()},{connection.name} with params '
            + "; ".join(param_descriptions)
        )

from importlib import resources

from mcp.types import ToolAnnotations
import yaml

from gerbera_sdk.firmware.devices.base import BaseFirmwareBuilder
from gerbera_sdk.firmware.devices.config_schema import (
    CommandConfig,
    DeviceConfig,
)
from gerbera_sdk.firmware.firmware_schema import (
    ColumnSpec,
    CommandSpec,
    LibrarySpec,
    ParameterSpec,
    PinModeSpec,
)
from gerbera_sdk.models.hardware.connection import Connection


class ConfigFirmwareBuilder(BaseFirmwareBuilder):
    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self.supports_streaming = config.capabilities.streaming

    def required_libraries(self) -> list[LibrarySpec]:
        return [
            LibrarySpec(include=library.include, install=library.install)
            for library in self.config.libraries
        ]

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        self._validate_required_pins(connection)
        return [
            PinModeSpec(pin=connection.pins[name], mode=pin.mode)
            for name, pin in self.config.pins.items()
        ]

    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        return [
            self._command_spec(command)
            for command in self.config.commands
            if self._command_enabled(command, connection)
        ]

    def annotations(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> ToolAnnotations:
        self._validate_required_pins(connection)
        command_config = self._command_config(command.method, connection)
        annotations = command_config.annotations
        return ToolAnnotations(
            title=self._render(annotations.title, connection),
            readOnlyHint=annotations.read_only_hint,
            openWorldHint=annotations.open_world_hint,
        )

    def state_definitions(self) -> dict[str, dict[str, str | None]]:
        return {"units": self.config.state.units}

    def stream_schema(self, connection: Connection) -> dict[str, ColumnSpec]:
        _ = connection
        return {
            name: ColumnSpec(
                type=column.type,
                idx=column.idx,
                primary_key=column.primary_key,
                nullable=column.nullable,
                default=column.default,
                sql_suffix=column.sql_suffix,
            )
            for name, column in self.config.stream.schema.items()
        }

    def build_definitions(self, connection: Connection) -> str:
        self._validate_required_pins(connection)
        definitions = [self.config.firmware.definitions]
        if connection.stream_enabled:
            definitions.append(self.config.firmware.definitions_when_streaming)
        return self._render_blocks(definitions, connection)

    def build_setup_lines(self, connection: Connection) -> list[str]:
        self._validate_required_pins(connection)
        lines = list(self.config.firmware.setup)
        if connection.stream_enabled:
            lines.extend(self.config.firmware.setup_when_streaming)
        return [self._indent_setup_line(self._render(line, connection)) for line in lines]

    def build_stream_lines(self, connection: Connection) -> list[str]:
        self._validate_required_pins(connection)
        if not connection.stream_enabled:
            return []
        if not self.supports_streaming:
            raise ValueError(
                f"{connection.component_type} does not support streaming"
            )

        stream_loop = self.config.firmware.stream_loop_when_streaming
        if not stream_loop:
            raise ValueError(
                "Missing stream loop for streaming device: "
                f"{self.config.component_type}"
            )

        return [
            self._indent_loop_line(line)
            for line in self._render(stream_loop, connection).splitlines()
        ]

    def build_handler(self, connection: Connection) -> str:
        self._validate_required_pins(connection)
        handler_name = "streaming" if connection.stream_enabled else "default"
        template = self.config.firmware.handlers.get(handler_name)
        if template is None:
            raise ValueError(
                f"Missing {handler_name} firmware handler for "
                f"{self.config.component_type}"
            )

        return self._render(template, connection)

    def _command_config(
        self,
        method: str,
        connection: Connection,
    ) -> CommandConfig:
        normalized_method = method.strip().upper()
        for command in self.config.commands:
            if (
                command.method.strip().upper() == normalized_method
                and self._command_enabled(command, connection)
            ):
                return command

        raise ValueError(
            f"Unsupported {self.config.component_type} command: {method}"
        )

    def _command_spec(self, command: CommandConfig) -> CommandSpec:
        return CommandSpec(
            method=command.method,
            description=command.description,
            params={
                name: ParameterSpec(
                    required=parameter.required,
                    description=parameter.description,
                    min=parameter.min,
                    max=parameter.max,
                )
                for name, parameter in command.params.items()
            },
        )

    def _validate_required_pins(self, connection: Connection) -> None:
        missing_pins = [
            pin_name
            for pin_name in self.config.pins
            if pin_name not in connection.pins
        ]
        if missing_pins:
            missing = ", ".join(missing_pins)
            raise ValueError(
                f"Missing required pin(s) for {self.config.component_type}: "
                f"{missing}"
            )

    @staticmethod
    def _command_enabled(
        command: CommandConfig,
        connection: Connection,
    ) -> bool:
        if command.enabled_when == "always":
            return True
        if command.enabled_when == "stream_enabled":
            return connection.stream_enabled
        raise ValueError(f"Unsupported command condition: {command.enabled_when}")

    def _render_blocks(
        self,
        blocks: list[str],
        connection: Connection,
    ) -> str:
        rendered = [
            self._render(block, connection).strip()
            for block in blocks
            if block.strip()
        ]
        return "\n\n".join(rendered)

    def _render(self, template: str, connection: Connection) -> str:
        rendered = template.replace("{component_type}", self.config.component_type)
        rendered = rendered.replace("{connection.name}", connection.name)
        rendered = rendered.replace("{connection.event_name}", connection.event_name)

        for pin_name in self.config.pins:
            rendered = rendered.replace(
                f"{{pins.{pin_name}}}",
                connection.pins[pin_name],
            )

        if "{connection." in rendered or "{pins." in rendered:
            raise ValueError(
                f"Unsupported firmware template placeholder for "
                f"{self.config.component_type}"
            )

        return rendered

    @staticmethod
    def _indent_setup_line(line: str) -> str:
        if not line:
            return line
        if line.startswith("  "):
            return line
        return f"  {line}"

    @staticmethod
    def _indent_loop_line(line: str) -> str:
        if not line:
            return line
        return f"  {line}"


def load_device_config(component_type: str) -> DeviceConfig:
    config_ref = (
        resources.files("gerbera_sdk.firmware.devices.configs")
        / f"{component_type}.yaml"
    )
    if not config_ref.is_file():
        raise ValueError(f"Unsupported component type: {component_type}")

    with config_ref.open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    config = DeviceConfig.from_data(data)
    if config.component_type != component_type:
        raise ValueError(
            "Device config component_type does not match filename: "
            f"{config.component_type} != {component_type}"
        )
    return config

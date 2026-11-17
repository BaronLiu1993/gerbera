from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from importlib import resources

import yaml

from gerbera_sdk.firmware.devices.config_schema import (
    ColumnConfig,
    CommandConfig,
    DeviceConfig,
    LibraryConfig,
)
from gerbera_sdk.firmware.firmware_schema import PinModeSpec
from gerbera_sdk.models.hardware.connection import Connection


@dataclass(frozen=True)
class StreamContract:
    table_name: str
    schema: dict[str, ColumnConfig]


@dataclass(frozen=True)
class ConfigFirmwareBuilder:
    config: DeviceConfig

    @property
    def supports_streaming(self) -> bool:
        return self.config.capabilities.streaming

    def required_libraries(self) -> list[LibraryConfig]:
        return list(self.config.libraries)

    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        self.validate_required_pins(connection)
        return [
            PinModeSpec(pin=connection.pins[name], mode=pin.mode)
            for name, pin in self.config.pins.items()
        ]

    def required_commands(self, connection: Connection) -> list[CommandConfig]:
        return [
            command
            for command in self.config.commands
            if self.command_enabled(command, connection)
        ]


    def state_definitions(self) -> dict[str, dict[str, str | None]]:
        return {"units": {name: field.unit for name, field in self.config.state.fields.items()}}

    def stream_schema(self, connection: Connection) -> dict[str, ColumnConfig]:
        return dict(self.config.stream.schema)

    def build_stream_contract(
        self,
        connection: Connection,
    ) -> StreamContract | None:
        if not connection.stream_enabled:
            return None

        if not self.supports_streaming:
            raise ValueError(
                f"{connection.component_type} does not support streaming"
            )

        return StreamContract(
            table_name=connection.event_name,
            schema=self.stream_schema(connection),
        )

    def build_definitions(self, connection: Connection) -> str:
        self.validate_required_pins(connection)
        definitions = [self.config.firmware.definitions]
        if connection.stream_enabled:
            definitions.append(self.config.firmware.definitions_when_streaming)
        return self.render_blocks(definitions, connection)

    def build_setup_lines(self, connection: Connection) -> list[str]:
        self.validate_required_pins(connection)
        lines = list(self.config.firmware.setup)
        if connection.stream_enabled:
            lines.extend(self.config.firmware.setup_when_streaming)
        return [self.indent_setup_line(self.render(line, connection)) for line in lines]

    def build_stream_lines(self, connection: Connection) -> list[str]:
        self.validate_required_pins(connection)
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
            self.indent_loop_line(line)
            for line in self.render(stream_loop, connection).splitlines()
        ]

    def build_handler(self, connection: Connection) -> str:
        self.validate_required_pins(connection)
        handler_name = "streaming" if connection.stream_enabled else "default"
        template = self.config.firmware.handlers.get(handler_name)
        if template is None:
            raise ValueError(
                f"Missing {handler_name} firmware handler for "
                f"{self.config.component_type}"
            )

        return self.render(template, connection)

    def command_config(
        self,
        method: str,
        connection: Connection,
    ) -> CommandConfig:
        normalized_method = method.strip().upper()
        for command in self.config.commands:
            if (
                command.method.strip().upper() == normalized_method
                and self.command_enabled(command, connection)
            ):
                return command

        raise ValueError(
            f"Unsupported {self.config.component_type} command: {method}"
        )

    def validate_required_pins(self, connection: Connection) -> None:
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
    def command_enabled(
        command: CommandConfig,
        connection: Connection,
    ) -> bool:
        if command.enabled_when == "always":
            return True
        if command.enabled_when == "stream_enabled":
            return connection.stream_enabled
        raise ValueError(f"Unsupported command condition: {command.enabled_when}")

    def render_blocks(
        self,
        blocks: list[str],
        connection: Connection,
    ) -> str:
        rendered = [
            self.render(block, connection).strip()
            for block in blocks
            if block.strip()
        ]
        return "\n\n".join(rendered)

    def render(self, template: str, connection: Connection) -> str:
        rendered = template.replace("{component_type}", self.config.component_type)
        rendered = rendered.replace("{connection.name}", connection.name)
        rendered = rendered.replace("{connection.event_name}", connection.event_name)

        for pin_name in self.config.pins:
            rendered = rendered.replace(
                f"{{pins.{pin_name}}}",
                str(connection.pins[pin_name]),
            )

        if "{connection." in rendered or "{pins." in rendered:
            raise ValueError(
                f"Unsupported firmware template placeholder for "
                f"{self.config.component_type}"
            )

        return rendered

    @staticmethod
    def indent_setup_line(line: str) -> str:
        if not line:
            return line
        if line.startswith("  "):
            return line
        return f"  {line}"

    @staticmethod
    def indent_loop_line(line: str) -> str:
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
        data = yaml.safe_load(config_file.read())

    config = DeviceConfig.from_data(data)
    if config.component_type != component_type:
        raise ValueError(
            "Device config component_type does not match filename: "
            f"{config.component_type} != {component_type}"
        )
    return config


@dataclass(frozen=True)
class DeviceDefinition:
    component_type: str
    config: DeviceConfig


@dataclass(frozen=True)
class DeviceRegistry:
    definitions: tuple[DeviceDefinition, ...]
    definitions_by_type: Mapping[str, DeviceDefinition] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definitions_by_type",
            MappingProxyType(
                {
                    definition.component_type: definition
                    for definition in self.definitions
                }
            ),
        )

    def get_builder(
        self,
        component_type: str,
    ) -> ConfigFirmwareBuilder:
        return ConfigFirmwareBuilder(self.get_definition(component_type).config)

    def get_definition(self, component_type: str) -> DeviceDefinition:
        try:
            return self.definitions_by_type[component_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported component type: {component_type}"
            ) from exc


def load_device_definition(component_type: str) -> DeviceDefinition:
    return DeviceDefinition(
        component_type=component_type,
        config=load_device_config(component_type),
    )


DEVICE_DEFINITIONS = (
    load_device_definition("dcmotor"),
    load_device_definition("hcsr04"),
    load_device_definition("hw201"),
    load_device_definition("ky033"),
    load_device_definition("led"),
    load_device_definition("mg996r"),
    load_device_definition("sg90"),
)

DEVICE_REGISTRY = DeviceRegistry(DEVICE_DEFINITIONS)


def get_device_builder(component_type: str):
    return DEVICE_REGISTRY.get_builder(component_type)


def command_specs(connection: Connection) -> list[CommandConfig]:
    return get_device_builder(connection.component_type).required_commands(connection)

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from string import Template

from gerbera_sdk.firmware.boards import BOARD_REGISTRY
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.firmware.firmware_schema import BoardTransportKind, MAX_SERIAL_MESSAGE_BYTES
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.paths import FIRMWARE_PATH


@dataclass(frozen=True)
class FirmwareFiles:
    sketch: str

    def named_files(self, sketch_name: str) -> dict[str, str]:
        return {
            f"{sketch_name}.ino": self.sketch,
        }


@dataclass(frozen=True)
class FirmwareGenerator:
    board: Microcontroller

    def generate(self) -> FirmwareFiles:
        board_definition = BOARD_REGISTRY.get_definition(self.board.fqbn)
        includes = list(board_definition.includes)
        definitions = []
        setup = []
        streams = []
        handlers = []
        dispatch = []

        for connection in self.board.connections:
            builder = get_device_builder(connection.component_type)
            includes.extend(library.include for library in builder.required_libraries())
            definitions.append(builder.build_definitions(connection))
            setup.extend(f"  pinMode({pin.pin}, {pin.mode.value});" for pin in builder.pin_modes(connection))
            setup.extend(builder.build_setup_lines(connection))
            inactive_output = builder.render(builder.config.verification.safe_stop, connection)
            setup.extend(f"  {line}" for line in inactive_output.splitlines())
            streams.extend(builder.build_stream_lines(connection))
            handlers.append(builder.build_handler(connection))
            for command in builder.required_commands(connection):
                dispatch.append(
                    f'  if (action == "{command.method.upper()}" && commandName == "{connection.name}") '
                    f'{{ handle_{connection.name}(input); return; }}'
                )

        transport_definition = "#define GERBERA_TRANSPORT Serial"
        transport_setup = f"  GERBERA_TRANSPORT.begin({self.board.baud_rate});"
        if self.board.runtime_transport.kind == BoardTransportKind.BLUETOOTH_CLASSIC:
            includes.append("BluetoothSerial.h")
            transport_definition = "BluetoothSerial GERBERA_TRANSPORT;"
            device_name = json.dumps(self.board.runtime_transport.device_name)
            transport_setup = f"  GERBERA_TRANSPORT.begin({device_name});"

        package = resources.files("gerbera_sdk.firmware")
        template = Template(package.joinpath("sketch.ino.template").read_text())
        sketch = template.substitute(
            includes="\n".join(f"#include <{name}>" for name in dict.fromkeys(includes)),
            transport_definition=transport_definition,
            transport_setup=transport_setup,
            definitions="\n".join(definitions),
            setup="\n".join(setup),
            streams="\n".join(streams),
            handlers="\n\n".join(handlers),
            dispatch="\n".join(dispatch),
            max_message_bytes=MAX_SERIAL_MESSAGE_BYTES,
        )
        return FirmwareFiles(sketch)

    def write_files(self) -> Path:
        directory = FIRMWARE_PATH / self.board.id
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("GerberaRuntime.h", "GerberaRuntime.cpp", "Components.h", "Components.cpp",
                     "DeviceCommands.h", "DeviceCommands.cpp", "SerialCommands.h"):
            (directory / name).unlink(missing_ok=True)
        for name, source in self.generate().named_files(self.board.id).items():
            (directory / name).write_text(source)
        return directory / f"{self.board.id}.ino"

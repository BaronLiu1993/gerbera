from dataclasses import dataclass, field

from gerbera_sdk.firmware.source_builders import (
    ComponentSourceBuilder,
    DeviceCommandSourceBuilder,
    RuntimeSourceBuilder,
)
from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler


@dataclass(frozen=True)
class FirmwareFiles:
    sketch: str
    runtime_header: str
    runtime_source: str
    components_header: str
    components_source: str
    commands_header: str
    commands_source: str

    def named_files(self, sketch_name: str) -> dict[str, str]:
        return {
            f"{sketch_name}.ino": self.sketch,
            "GerberaRuntime.h": self.runtime_header,
            "GerberaRuntime.cpp": self.runtime_source,
            "Components.h": self.components_header,
            "Components.cpp": self.components_source,
            "DeviceCommands.h": self.commands_header,
            "DeviceCommands.cpp": self.commands_source,
        }


@dataclass(frozen=True)
class FirmwareGenerator:
    board: ResolvedBoard | Microcontroller
    resolved_board: ResolvedBoard = field(init=False)

    def __post_init__(self) -> None:
        resolved_board = (
            self.board
            if isinstance(self.board, ResolvedBoard)
            else HardwareContractCompiler.compile_microcontroller(self.board)
        )
        object.__setattr__(self, "resolved_board", resolved_board)

    def generate(self) -> FirmwareFiles:
        runtime = RuntimeSourceBuilder(self.resolved_board)
        components = ComponentSourceBuilder(self.resolved_board)
        commands = DeviceCommandSourceBuilder(self.resolved_board)
        return FirmwareFiles(
            sketch=runtime.build_sketch(),
            runtime_header=runtime.build_header(),
            runtime_source=runtime.build_source(),
            components_header=components.build_header(),
            components_source=components.build_source(),
            commands_header=commands.build_header(),
            commands_source=commands.build_source(),
        )

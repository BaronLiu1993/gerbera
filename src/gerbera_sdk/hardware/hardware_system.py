from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from gerbera_sdk.firmware.flasher import DEFAULT_FIRMWARE_ROOT, Flasher
from gerbera_sdk.firmware.generator import FirmwareGenerator
from gerbera_sdk.hardware.microcontroller import Microcontroller
from gerbera_sdk.transport.runtime import ConnectionRuntime


@dataclass
class HardwareSystem:
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)

    def add_microcontroller(self, microcontroller: Microcontroller) -> bool:
        if microcontroller.id in self._get_microcontroller_ids():
            return False

        self.microcontrollers.append(microcontroller)
        return True

    def get_microcontroller(self, microcontroller_id: str) -> Microcontroller:
        for microcontroller in self.microcontrollers:
            if microcontroller.id == microcontroller_id:
                return microcontroller

        raise ValueError(f"Unknown microcontroller id: {microcontroller_id}")

    def build_read_command(self, microcontroller_id: str, connection_name: str) -> str:
        microcontroller = self.get_microcontroller(microcontroller_id)
        return ConnectionRuntime.build_read_command(
            microcontroller.get_connection(connection_name)
        )

    def compile(
        self,
        sketch_root: Path = DEFAULT_FIRMWARE_ROOT,
    ) -> dict[str, dict[str, Any]]:
        sketch_paths = self.generate_sketches(sketch_root)
        compiled_artifacts: dict[str, dict[str, Any]] = {}

        for microcontroller in self.microcontrollers:
            compiled_artifacts[microcontroller.id] = {
                "firmware": FirmwareGenerator.generate(microcontroller),
                "sketch_path": sketch_paths[microcontroller.id],
            }

        return compiled_artifacts

    def prepare_command(
        self,
        microcontroller_id: str,
        connection_name: str,
    ) -> dict[str, Union[str, int]]:
        microcontroller = self.get_microcontroller(microcontroller_id)
        board_information = microcontroller.get_board_information()

        return {
            "microcontroller_id": microcontroller.id,
            "connection_name": connection_name,
            "port": board_information["port"],
            "protocol": board_information["protocol"],
            "protocol_label": board_information["protocol_label"],
            "baud_rate": microcontroller.baud_rate,
            "command": self.build_read_command(
                microcontroller_id=microcontroller_id,
                connection_name=connection_name,
            ),
        }

    def parse_response(self, response: str) -> dict[str, Any]:
        return ConnectionRuntime.parse_response(response)

    def generate_sketches(
        self,
        sketch_root: Path = DEFAULT_FIRMWARE_ROOT,
    ) -> dict[str, Path]:
        sketch_paths: dict[str, Path] = {}

        for microcontroller in self.microcontrollers:
            sketch_paths[microcontroller.id] = FirmwareGenerator.write_sketch(
                microcontroller,
                sketch_root,
            )

        return sketch_paths

    def flash_microcontrollers(
        self,
        fqbn_by_microcontroller_id: dict[str, str],
        sketch_root: Path = DEFAULT_FIRMWARE_ROOT,
    ) -> dict[str, Path]:
        sketch_paths: dict[str, Path] = {}

        for microcontroller in self.microcontrollers:
            if microcontroller.id not in fqbn_by_microcontroller_id:
                raise ValueError(
                    f"Missing fqbn for microcontroller: {microcontroller.id}"
                )

            sketch_paths[microcontroller.id] = Flasher.flash_microcontroller(
                microcontroller=microcontroller,
                fqbn=fqbn_by_microcontroller_id[microcontroller.id],
                sketch_root=sketch_root,
            )

        return sketch_paths

    def _get_microcontroller_ids(self) -> set[str]:
        return {
            microcontroller.id
            for microcontroller in self.microcontrollers
        }

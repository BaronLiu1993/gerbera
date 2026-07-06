from dataclasses import dataclass, field
from pathlib import Path

from gerbera_sdk.firmware.flasher import Flasher
from gerbera_sdk.firmware.generator import FirmwareGenerator
from gerbera_sdk.hardware.microcontroller import Microcontroller


@dataclass
class HardwareSystem:
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)

    def add_microcontroller(self, microcontroller: Microcontroller) -> bool:
        if microcontroller.id in self._get_microcontroller_ids():
            return False

        self.microcontrollers.append(microcontroller)
        return True

    def generate_sketches(self, sketch_root: Path) -> dict[str, Path]:
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
        sketch_root: Path,
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

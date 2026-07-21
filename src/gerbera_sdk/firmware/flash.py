import subprocess
import shutil
from pathlib import Path

from gerbera_sdk.firmware.generator import Generator
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem

DEFAULT_BUILD_DIRNAME = "build"


class Flash:
    @staticmethod
    def generate_files(hardware_system: HardwareSystem) -> dict[str, Path]:
        sketch_paths: dict[str, Path] = {}

        for microcontroller in hardware_system.microcontrollers:
            firmware_code = Generator.build_firmware(microcontroller)
            microcontroller_root = Path(microcontroller.id)
            microcontroller_root.mkdir(parents=True, exist_ok=True)
            sketch_path = microcontroller_root / f"{microcontroller.id}.ino"
            sketch_path.write_text(firmware_code)
            sketch_paths[microcontroller.id] = sketch_path

        return sketch_paths

    @staticmethod
    def flash_code(hardware_system: HardwareSystem) -> None:
        try:
            sketch_paths = Flash.generate_files(hardware_system)

            for microcontroller in hardware_system.microcontrollers:
                port = microcontroller.port
                fqbn = microcontroller.fqbn
                sketch_path = sketch_paths[microcontroller.id]
                microcontroller_root = sketch_path.parent
                build_path = microcontroller_root / DEFAULT_BUILD_DIRNAME

                if build_path.exists():
                    shutil.rmtree(build_path)

                build_path.mkdir(parents=True, exist_ok=True)

                subprocess.run([
                    "arduino-cli", "compile",
                    "--fqbn", fqbn,
                    "--build-path", str(build_path),
                    str(microcontroller_root),
                ], check=True)

                subprocess.run([
                    "arduino-cli", "upload",
                    "-p", port,
                    "--fqbn", fqbn,
                    "--input-dir", str(build_path),
                    str(microcontroller_root),
                ], check=True)

        except Exception as e:
            raise RuntimeError(f"Failed to flash hardware system {hardware_system.id}") from e

    @staticmethod
    def flash(hardware_system: HardwareSystem) -> None:
        Flash.flash_code(hardware_system)

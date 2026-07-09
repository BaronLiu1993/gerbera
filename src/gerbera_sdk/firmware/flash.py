import subprocess
import shutil
from pathlib import Path

from gerbera_sdk.firmware.generator import Generator
from gerbera_sdk.models.hardware_system import HardwareSystem

DEFAULT_BUILD_DIRNAME = "build"


class Flash:
    @staticmethod
    def generate_files(hardware_system: HardwareSystem) -> dict[str, str]:
        generated_files: dict[str, str] = {}

        for microcontroller in hardware_system.microcontrollers:
            firmware_code = Generator.build_firmware(microcontroller)
            sketch_dir = Path(microcontroller.id)
            sketch_dir.mkdir(parents=True, exist_ok=True)
            sketch_path = sketch_dir / f"{microcontroller.id}.ino"
            sketch_path.write_text(firmware_code)
            microcontroller.set_firmware_file(str(sketch_dir))
            generated_files[microcontroller.id] = str(sketch_dir)

        return generated_files

    @staticmethod
    def flash_code(hardware_system: HardwareSystem) -> None:
        try:
            Flash.generate_files(hardware_system)

            for microcontroller in hardware_system.microcontrollers:
                port = microcontroller.port
                fqbn = microcontroller.fqbn
                sketch_path = microcontroller.firmware_file_path
                build_path = Path(microcontroller.id) / DEFAULT_BUILD_DIRNAME

                if not sketch_path:
                    raise ValueError(
                        f"Missing firmware file path for microcontroller {microcontroller.id}"
                    )

                if build_path.exists():
                    shutil.rmtree(build_path)

                build_path.mkdir(parents=True, exist_ok=True)

                subprocess.run([
                    "arduino-cli", "compile",
                    "--fqbn", fqbn,
                    "--build-path", str(build_path),
                    sketch_path
                ], check=True)

                subprocess.run([
                    "arduino-cli", "upload",
                    "-p", port,
                    "--fqbn", fqbn,
                    "--input-dir", str(build_path),
                    sketch_path
                ], check=True)

        except Exception as e:
            raise RuntimeError(f"Failed to flash hardware system {hardware_system.id}") from e

    @staticmethod
    def flash(hardware_system) -> None:
        Flash.flash_code(hardware_system)

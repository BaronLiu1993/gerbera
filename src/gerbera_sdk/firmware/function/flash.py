import subprocess
from pathlib import Path

from gerbera_sdk.firmware.function.generator import Generator
from gerbera_sdk.models.hardware_system import HardwareSystem

DEFAULT_FIRMWARE_ROOT = Path("gerbera_firmware")


class Flash:
    @staticmethod
    def generate_files(hardware_system: HardwareSystem) -> dict[str, str]:
        DEFAULT_FIRMWARE_ROOT.mkdir(parents=True, exist_ok=True)
        generated_files: dict[str, str] = {}

        for microcontroller in hardware_system.microcontrollers:
            firmware_code = Generator.build_firmware(microcontroller)
            sketch_path = DEFAULT_FIRMWARE_ROOT / f"{microcontroller.id}.ino"
            sketch_path.write_text(firmware_code)
            microcontroller.set_firmware_file(str(sketch_path))
            generated_files[microcontroller.id] = str(sketch_path)

        return generated_files

    @staticmethod
    def flash_code(hardware_system: HardwareSystem) -> None:
        try:
            Flash.generate_files(hardware_system)

            for microcontroller in hardware_system.microcontrollers:
                port = microcontroller.port
                fqbn = microcontroller.fqbn
                sketch_path = microcontroller.firmware_file_path

                if not sketch_path:
                    raise ValueError(
                        f"Missing firmware file path for microcontroller {microcontroller.id}"
                    )

                subprocess.run([
                    "arduino-cli", "compile",
                    "--fqbn", fqbn,
                    sketch_path
                ], check=True)

                subprocess.run([
                    "arduino-cli", "upload",
                    "-p", port,
                    "--fqbn", fqbn,
                    sketch_path
                ], check=True)

        except Exception as e:
            raise RuntimeError(f"Failed to flash hardware system {hardware_system.id}") from e
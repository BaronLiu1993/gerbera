import subprocess
from pathlib import Path

from gerbera_sdk.firmware.generator import FirmwareGenerator
from gerbera_sdk.hardware.microcontroller import Microcontroller


class Flasher:
    @staticmethod
    def flashCode(port: str, fqbn: str, sketch_path: str) -> None:
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

    @staticmethod
    def flash_microcontroller(
        microcontroller: Microcontroller,
        fqbn: str,
        sketch_root: Path,
    ) -> Path:
        board_information = microcontroller.get_board_information()
        sketch_path = FirmwareGenerator.write_sketch(microcontroller, sketch_root)
        Flasher.flashCode(
            port=board_information["port"],
            fqbn=fqbn,
            sketch_path=str(sketch_path),
        )
        return sketch_path

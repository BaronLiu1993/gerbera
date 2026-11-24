import json
import shutil
from dataclasses import dataclass
from pathlib import Path
import subprocess

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
    from gerbera_sdk.models.hardware.microcontroller import Microcontroller


@dataclass(frozen=True)
class FirmwareUploader:
    board: "Microcontroller"

    def compile(self, sketch_path: Path) -> Path:
        if not sketch_path.is_file():
            raise FileNotFoundError(f"Generated firmware sketch not found: {sketch_path}")
        build_path = sketch_path.parent / "build"
        if build_path.exists():
            shutil.rmtree(build_path)
        build_path.mkdir(parents=True)
        subprocess.run([
            "arduino-cli", "compile",
            "--fqbn", self.board.fqbn,
            "--build-path", str(build_path),
            str(sketch_path.parent),
        ], check=True)
        return build_path

    def upload(self, build_path: Path) -> None:
        if not build_path.is_dir():
            raise FileNotFoundError(f"Compiled firmware directory not found: {build_path}")
        subprocess.run([
            "arduino-cli", "upload",
            "-p", self.board.upload_port,
            "--fqbn", self.board.fqbn,
            "--input-dir", str(build_path),
            str(build_path.parent),
        ], check=True)

    @staticmethod
    def install_dependencies(hardware_system: "HardwareSystem") -> None:
        required_cores: set[str] = set()
        required_libraries: set[str] = set()
        for board in hardware_system.microcontrollers:
            required_cores.add(":".join(board.fqbn.split(":")[:2]))
            for connection in board.connections:
                if connection.library is not None:
                    required_libraries.add(connection.library)

        cores = FirmwareUploader.read_inventory("core")
        libraries = FirmwareUploader.read_inventory("lib")
        for name in sorted(required_cores - cores):
            subprocess.run(["arduino-cli", "core", "install", name], check=True)

        for name in sorted(required_libraries - libraries):
            subprocess.run(["arduino-cli", "lib", "install", name], check=True)

    @staticmethod
    def read_inventory(kind: str) -> set[str]:
        result = subprocess.run(
            ["arduino-cli", kind, "list", "--format", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        inventory = json.loads(result.stdout)
        if kind == "core":
            return {
                platform["id"]
                for platform in inventory["platforms"]
                if platform.get("installed_version")
            }
        return {
            entry["library"]["name"] for entry in inventory["installed_libraries"]
        }

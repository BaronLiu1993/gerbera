from dataclasses import dataclass
from pathlib import Path
import subprocess

from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard


@dataclass(frozen=True)
class FirmwareUploader:
    board: ResolvedBoard

    def upload(self, build_path: Path) -> None:
        if not build_path.is_dir():
            raise FileNotFoundError(f"Compiled firmware directory not found: {build_path}")
        subprocess.run([
            "arduino-cli", "upload",
            "-p", self.board.firmware_upload_port,
            "--fqbn", self.board.fqbn,
            "--input-dir", str(build_path),
            str(build_path.parent),
        ], check=True)

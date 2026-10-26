from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from gerbera_sdk.models.hardware.hardware_plan import ResolvedBoard


@dataclass(frozen=True)
class FirmwareCompiler:
    board: ResolvedBoard

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

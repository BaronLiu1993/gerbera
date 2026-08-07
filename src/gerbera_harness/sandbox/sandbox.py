import subprocess
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class Sandbox:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tmp_dir: Path = Path(".tmp")

    @property
    def run_dir(self) -> Path:
        return self.tmp_dir / self.run_id

    # writes file and the folder
    def write_executable(self, code: str, name: str) -> Path:
        script_path = self.run_dir / name
        self.run_dir.mkdir(parents=True)

        try:
            script_path.write_text(code)
        except OSError as exc:
            self.delete_executable()
            raise ValueError("Failed to write script") from exc

        return script_path

    # Deletes the entire folder
    def delete_executable(self) -> None:
        shutil.rmtree(self.run_dir, ignore_errors=True)

    def run(
        self,
        code: str,
        name: str,
        command: list[str],
        max_time: float = 30.0,
    ) -> object:
        self.write_executable(code, name)
        try:
            raw_subprocess_output = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=max_time,
            )
            return json.load(raw_subprocess_output)
        except subprocess.SubprocessError:
            raise RuntimeError("Failed To Execute Script")
        finally:
            self.delete_executable()

import subprocess
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Literal
from enum import Enum

from gerbera_harness.sandbox.database_gateway import DatabaseGateway


@dataclass
class Sandbox:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    database_gateway: DatabaseGateway
    tmp_dir: Path = Path(".tmp")

    @property
    def run_dir(self) -> Path:
        return self.tmp_dir / self.run_id

    # We need to pass in commands for SQL query,
    def run_query(self, query: str):
        self.database_gateway.query(query)

    # Script Execution
    def _write_executable(self, code: str, name: str) -> Path:
        script_path = self.run_dir / name
        self.run_dir.mkdir(parents=True)

        try:
            script_path.write_text(code)
        except OSError as exc:
            self.delete_executable()
            raise ValueError("Failed to write script") from exc

        return script_path

    # Deletes the entire folder
    def _delete_executable(self) -> None:
        shutil.rmtree(self.run_dir, ignore_errors=True)

    # Execute and capture the response from a long running script
    def run_script(
        self,
        code: str,
        name: str,
        command: list[str],
        max_time: float = 30.0,
    ) -> object:
        self._write_executable(code, name)
        try:
            raw_subprocess_output = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=max_time,
            )
            return json.loads(raw_subprocess_output)
        except subprocess.SubprocessError:
            raise RuntimeError("Failed To Execute Script")
        finally:
            self._delete_executable()

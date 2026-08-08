import json
import subprocess
import uuid
from typing import Any
from dataclasses import dataclass, field


@dataclass
class SandboxResult:
    session_id: str
    run_id: str
    result: Any


@dataclass
class SandboxGateway:
    @staticmethod
    def build_image(self) -> None:
        try:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    "src/gerbera_harness/sandbox.Dockerfile",
                    "-t",
                    "sandbox:latest",
                    "src/gerbera_harness",
                ],
                check=True,
                timeout=60.0,
            )

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Sandbox image build timed out") from exc

        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Failed to build sandbox image") from exc

    @staticmethod
    def run_sandbox(
        self,
        session_id: str,
        code: str,
    ) -> SandboxResult:

        run_id = str(uuid.uuid4())

        sandbox = Sandbox(
            session_id=session_id,
            run_id=run_id,
        )

        try:
            result = sandbox.run_container(code)

            return SandboxResult(
                session_id=session_id,
                run_id=run_id,
                result=result,
            )

        except Exception as exc:
            raise ValueError("Failed To Run Container") from exc


@dataclass
class Sandbox:
    session_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout: float = 30.0
    container_image: str = "sandbox:latest"

    def run_container(self, code: str) -> object:
        container_name = f"gerbera-{uuid.uuid4()}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "64",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--tmpfs",
            "/tmp:size=64m",
            "--user",
            "10001:10001",
            self.container_image,
            "python3",
            "-c",
            code,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout,
            )

            return json.loads(result.stdout)

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Sandbox execution timed out") from exc

        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Sandbox execution failed: {exc.stderr}") from exc

        finally:
            subprocess.run(
                [
                    "docker",
                    "rm",
                    "-f",
                    container_name,
                ],
                capture_output=True,
                text=True,
            )

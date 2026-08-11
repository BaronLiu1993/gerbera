import json
import subprocess
import uuid
from typing import Any
from dataclasses import dataclass, field

SANDBOX_IMAGE = "ghcr.io/baronliu1993/gerbera-sandbox:latest"


@dataclass
class SandboxResult:
    run_id: str
    result: Any

# In the future if we ever want to add additional protection
@dataclass
class SandboxGateway:
    @staticmethod
    def run_sandbox(
        code: str,
    ) -> SandboxResult:
        sandbox = Sandbox()
        try:
            result = sandbox.run_container(code)
            return result
        except Exception as exc:
            raise ValueError("Failed To Run Container") from exc


@dataclass
class Sandbox:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout: float = 30.0
    container_image: str = SANDBOX_IMAGE

    def run_container(self, code: str) -> SandboxResult:
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

            return SandboxResult(run_id=self.run_id, result=json.loads(result.stdout))

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

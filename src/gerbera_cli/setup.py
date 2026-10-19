from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from gerbera_cli.configuration import ProjectConfig
from gerbera_cli.deployment import StartupStage

RUNTIME_PATH = Path(".gerbera/runtime")
LOGS_PATH = Path(".gerbera/logs")
POLL_INTERVAL_SECONDS = 0.25
SHUTDOWN_TIMEOUT_SECONDS = 10


@dataclass
class LocalProjectServices:
    config: ProjectConfig
    project_id: str = field(default_factory=lambda: hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:12])

    @property
    def network(self) -> str:
        return f"gerbera-{self.project_id}"

    def container_name(self, service: str) -> str:
        return f"gerbera-{self.project_id}-{service}"

    def container_status(self, service: str) -> dict | None:
        result = subprocess.run(
            ["docker", "inspect", self.container_name(service)], capture_output=True, text=True,
        )
        if result.returncode:
            return None
        metadata = json.loads(result.stdout)[0]
        if metadata.get("Config", {}).get("Labels", {}).get("gerbera.project") != self.project_id:
            raise RuntimeError("Refusing to manage a container owned by another deployment")
        return metadata

    def start_database(self) -> bool:
        return self.start_container("database")

    def start_container(self, name: str) -> bool:
        service = self.config.services.get(name)
        if service is None or not service.enabled or not service.managed:
            return False
        metadata = self.container_status(name)
        if metadata is not None:
            if metadata["State"]["Running"]:
                return False
            subprocess.run(["docker", "start", self.container_name(name)], check=True)
            return True
        self.ensure_network()
        subprocess.run(["docker", "pull", service.image], check=True)
        command = [
            "docker", "run", "-d", "--name", self.container_name(name),
            "--label", f"gerbera.project={self.project_id}", "--network", self.network,
            "--network-alias", f"gerbera-{name}", "--add-host", "host.docker.internal:host-gateway",
        ]
        address = urlsplit(service.url)
        if service.container_port:
            command.extend(("-p", f"{address.hostname}:{address.port}:{service.container_port}"))
        for env_file in service.env_files:
            command.extend(("--env-file", str(Path(env_file).resolve())))
        environment = dict(service.environment)
        if name == "harness":
            environment["MCP_URL"] = container_sdk_url(self.config.services["sdk"].url) + "/mcp"
            database = self.config.services.get("database")
            if database is not None and database.enabled:
                database_address = urlsplit(database.url)
                environment["GERBERA_DATABASE_HOST"] = (
                    "gerbera-database" if database.managed else
                    urlsplit(container_sdk_url(database.url)).hostname
                )
                environment["GERBERA_DATABASE_PORT"] = str(
                    database.container_port if database.managed else database_address.port or 5432
                )
        for key, value in environment.items():
            command.extend(("-e", f"{key}={value}"))
        if service.config:
            config_path = Path(service.config).resolve()
            command.extend(("-v", f"{config_path.parent}:/app/service-config:ro"))
            command.extend(("-e", f"GERBERA_HARNESS_CONFIG=/app/service-config/{config_path.name}"))
        if service.volume:
            command.extend(("-v", f"{service.volume}:/var/lib/postgresql/data"))
        command.append(service.image)
        subprocess.run(command, check=True)
        return True

    def ensure_network(self) -> None:
        result = subprocess.run(["docker", "network", "inspect", self.network], capture_output=True, text=True)
        if result.returncode:
            subprocess.run(["docker", "network", "create", "--label",
                            f"gerbera.project={self.project_id}", self.network], check=True)
        elif json.loads(result.stdout)[0].get("Labels", {}).get("gerbera.project") != self.project_id:
            raise RuntimeError("Refusing to reuse a network owned by another deployment")

    def sdk_command(self) -> list[str]:
        service = self.config.services["sdk"]
        address = urlsplit(service.url)
        return [
            sys.executable, "-m", "gerbera_sdk.server", "serve",
            "--config", str(service.config), "--host", service.bind_host or address.hostname or "127.0.0.1",
            "--port", str(address.port or 80),
        ]

    def sdk_environment(self) -> dict[str, str]:
        environment = os.environ | self.config.services["sdk"].environment
        database = self.config.services.get("database")
        if database is not None and database.enabled:
            address = urlsplit(database.url)
            environment["GERBERA_DATABASE_HOST"] = address.hostname or "127.0.0.1"
            environment["GERBERA_DATABASE_PORT"] = str(address.port or 5432)
        return environment

    def run_server_foreground(self) -> None:
        if not self.config.services["sdk"].managed:
            raise RuntimeError("The SDK is externally managed; start it on its own host")
        subprocess.run(self.sdk_command(), env=self.sdk_environment(), check=True)

    def start_server(self) -> bool:
        service = self.config.services["sdk"]
        if not service.enabled or not service.managed:
            return False
        if self.server_running():
            return False
        RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        with (LOGS_PATH / "server.log").open("a") as log_file:
            process = subprocess.Popen(
                self.sdk_command(), env=self.sdk_environment(), stdout=log_file,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
        try:
            started_at = process_identity(process.pid)
            (RUNTIME_PATH / "sdk.json").write_text(json.dumps({
                "pid": process.pid, "started_at": started_at, "project_id": self.project_id,
            }))
        except BaseException:
            process.terminate()
            process.wait()
            raise
        return True

    def server_running(self) -> bool:
        path = RUNTIME_PATH / "sdk.json"
        if not path.is_file():
            return False
        record = json.loads(path.read_text())
        if record["project_id"] != self.project_id:
            raise RuntimeError("Refusing to manage a process owned by another deployment")
        return process_identity(record["pid"]) == record["started_at"] and bool(record["started_at"])

    def wait_for_server(self) -> None:
        self.wait_for_service("sdk")

    def start_harness(self) -> bool:
        created = self.start_container("harness")
        service = self.config.services.get("harness")
        if service is None or not service.enabled:
            return False
        try:
            self.wait_for_service("harness")
        except BaseException:
            if created:
                self.stop_container("harness")
            raise
        return created

    def wait_for_service(self, name: str) -> None:
        service = self.config.services[name]
        deadline = time.monotonic() + self.config.startup_timeout_seconds
        report = {}
        while time.monotonic() < deadline:
            if service.managed:
                running = self.server_running() if name == "sdk" else bool(
                    (self.container_status(name) or {}).get("State", {}).get("Running")
                )
                if not running:
                    raise RuntimeError(f"{name} exited during startup; run gerbera logs")
            report = readiness_report(service.url)
            if report.get("ready") is True:
                return
            time.sleep(POLL_INTERVAL_SECONDS)
        raise TimeoutError(f"{name} did not report readiness: {report}")

    def stop_container(self, name: str) -> None:
        service = self.config.services.get(name)
        if service is None or not service.managed:
            return
        metadata = self.container_status(name)
        if metadata is not None and metadata["State"]["Running"]:
            subprocess.run(["docker", "stop", self.container_name(name)], check=True)

    def stop_server(self) -> None:
        if not self.config.services["sdk"].managed or not self.server_running():
            return
        record = json.loads((RUNTIME_PATH / "sdk.json").read_text())
        os.killpg(record["pid"], signal.SIGTERM)
        deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
        while self.server_running() and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
        if self.server_running():
            raise TimeoutError("SDK did not finish safe shutdown; inspect its logs before terminating it")

    def rollback(self, stages: tuple[StartupStage, ...]) -> None:
        for stage in stages:
            if stage is StartupStage.SERVER:
                self.stop_server()
            else:
                self.stop_container(stage.value)

    def stop(self) -> None:
        self.stop_container("harness")
        self.stop_server()
        self.stop_container("database")

    def status(self) -> dict[str, object]:
        return {
            name: readiness_report(service.url) if name != "database" else {
                "managed": service.managed,
                "running": bool((self.container_status(name) or {}).get("State", {}).get("Running")) if service.managed else None,
            }
            for name, service in self.config.services.items() if service.enabled
        }

    def doctor(self) -> dict[str, object]:
        return self.status()

    def logs(self, follow: bool) -> None:
        log_path = LOGS_PATH / "server.log"
        if log_path.exists():
            print(log_path.read_text(), end="")
        processes = []
        try:
            for name in ("database", "harness"):
                service = self.config.services.get(name)
                if service is not None and service.managed and self.container_status(name) is not None:
                    command = ["docker", "logs", "--tail", "100"]
                    if follow:
                        command.append("--follow")
                    processes.append(subprocess.Popen([*command, self.container_name(name)]))
            if follow and log_path.exists():
                processes.append(subprocess.Popen(["tail", "-f", str(log_path)]))
            for process in processes:
                process.wait()
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()


def process_identity(pid: int) -> str:
    result = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def readiness_report(url: str) -> dict:
    address = urlsplit(url)
    if address.hostname in {"0.0.0.0", "::"}:
        url = urlunsplit((address.scheme, f"127.0.0.1:{address.port}", address.path, "", ""))
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url.rstrip("/") + "/ready")
        if response.status_code not in {200, 503}:
            return {"ready": False, "status_code": response.status_code}
        payload = response.json()
        return payload if isinstance(payload, dict) else {"ready": False, "phase": "invalid_response"}
    except (httpx.HTTPError, ValueError):
        return {"ready": False, "phase": "unreachable"}


def container_sdk_url(url: str) -> str:
    address = urlsplit(url)
    if address.hostname in {"127.0.0.1", "localhost", "0.0.0.0", "::"}:
        return urlunsplit((address.scheme, f"host.docker.internal:{address.port or 80}", address.path, "", ""))
    return url.rstrip("/")

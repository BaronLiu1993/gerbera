from dataclasses import dataclass
import json
import subprocess

from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan


@dataclass(frozen=True)
class FirmwareDependencies:
    plan: HardwarePlan

    def install(self) -> None:
        cores = self.read_inventory("core")
        libraries = self.read_inventory("lib")
        required_cores = {name for board in self.plan.boards for name in board.definition.libraries}
        required_libraries = {
            library.install for board in self.plan.boards for connection in board.connections
            for library in connection.device_definition.config.libraries if library.install.strip()
        }
        for name in sorted(required_cores - cores):
            subprocess.run(["arduino-cli", "core", "install", name], check=True)
        for name in sorted(required_libraries - libraries):
            subprocess.run(["arduino-cli", "lib", "install", name], check=True)

    @staticmethod
    def read_inventory(kind: str) -> set[str]:
        result = subprocess.run(
            ["arduino-cli", kind, "list", "--format", "json"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError("Arduino CLI inventory must be an object")
        if kind == "core":
            entries = payload["platforms"]
            return {entry["id"] for entry in entries
                    if entry.get("installed_version")}
        entries = payload["installed_libraries"]
        return {entry["library"]["name"] for entry in entries}

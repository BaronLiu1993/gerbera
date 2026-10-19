from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedBoard
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime, FirmwareContractMismatch
from gerbera_sdk.paths import FIRMWARE_PATH


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
        if kind == "core":
            entries = payload if isinstance(payload, list) else payload["platforms"]
            return {entry["id"] for entry in entries
                    if entry.get("installed_version") or entry.get("installed") or entry.get("version")}
        entries = payload if isinstance(payload, list) else payload["installed_libraries"]
        return {entry["library"]["name"] for entry in entries}


@dataclass(frozen=True)
class InitialProvisioning:
    board: ResolvedBoard

    @property
    def path(self) -> Path:
        return FIRMWARE_PATH / self.board.microcontroller_id / "provisioning.json"

    def validate(self) -> None:
        if not self.path.is_file():
            raise RuntimeError(
                "Board did not answer a firmware handshake; automatic flashing is unsafe. "
                "Check power and transport. First-time provisioning must be authorized "
                "by SDK initialization on the machine connected to the board."
            )
        expected = {
            "microcontroller_id": self.board.microcontroller_id,
            "fqbn": self.board.fqbn,
            "upload_port": self.board.firmware_upload_port,
        }
        if json.loads(self.path.read_text()) != expected:
            raise RuntimeError("Initial provisioning target does not match the configured board")

    def consume(self) -> None:
        self.validate()
        self.path.unlink()


@dataclass(frozen=True)
class FirmwareReconciler:
    board_runtime: BoardRuntime

    def reconcile(self) -> None:
        changed = []
        provisioning = set()
        for board in self.board_runtime.hardware_plan.boards:
            try:
                self.inspect(board)
            except FirmwareContractMismatch:
                changed.append(board)
            except TimeoutError:
                InitialProvisioning(board).validate()
                provisioning.add(board.microcontroller_id)
                changed.append(board)
        if not changed:
            return
        FirmwareDependencies(self.board_runtime.hardware_plan).install()
        for board in changed:
            authorization = InitialProvisioning(board) if board.microcontroller_id in provisioning else None
            Flash.flash_boards(
                self.board_runtime.hardware_plan, (board,),
                before_upload=authorization.consume if authorization else None,
            )
            self.inspect(board)

    def inspect(self, board: ResolvedBoard) -> None:
        transport = self.board_runtime.transport_factory.create(board)
        try:
            transport.connect()
            BoardRuntime.verify_contract(board, transport)
        finally:
            transport.close()

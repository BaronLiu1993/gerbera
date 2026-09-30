import json
import shutil
import subprocess
from pathlib import Path

from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedBoard
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.paths import FIRMWARE_PATH

DEFAULT_BUILD_DIRNAME = "build"


class Flash:
    @staticmethod
    def generate_files(
        hardware: HardwareSystem | HardwarePlan,
    ) -> dict[str, Path]:
        hardware_plan = (
            hardware
            if isinstance(hardware, HardwarePlan)
            else HardwareContractCompiler.compile(hardware)
        )
        sketch_paths: dict[str, Path] = {}

        for board in hardware_plan.boards:
            firmware_files = FirmwareGenerator(board).generate()
            microcontroller_root = FIRMWARE_PATH / board.microcontroller_id
            microcontroller_root.mkdir(parents=True, exist_ok=True)
            for filename, source in firmware_files.named_files(
                board.microcontroller_id
            ).items():
                (microcontroller_root / filename).write_text(source)
            sketch_path = microcontroller_root / f"{board.microcontroller_id}.ino"
            sketch_paths[board.microcontroller_id] = sketch_path

        return sketch_paths

    @staticmethod
    def flash_code(hardware: HardwareSystem | HardwarePlan) -> None:
        hardware_plan = (
            hardware
            if isinstance(hardware, HardwarePlan)
            else HardwareContractCompiler.compile(hardware)
        )
        boards = tuple(
            board
            for board in hardware_plan.boards
            if not Flash.firmware_is_current(board)
        )
        Flash.flash_boards(hardware_plan, boards)

    @staticmethod
    def flash_all_code(hardware: HardwareSystem | HardwarePlan) -> None:
        hardware_plan = (
            hardware
            if isinstance(hardware, HardwarePlan)
            else HardwareContractCompiler.compile(hardware)
        )
        Flash.flash_boards(hardware_plan, hardware_plan.boards)

    @staticmethod
    def flash_boards(
        hardware_plan: HardwarePlan,
        boards: tuple[ResolvedBoard, ...],
    ) -> None:
        if not boards:
            return
        try:
            sketch_paths = Flash.generate_files(hardware_plan)

            for board in boards:
                port = board.firmware_upload_port
                fqbn = board.fqbn
                sketch_path = sketch_paths[board.microcontroller_id]
                microcontroller_root = sketch_path.parent
                build_path = microcontroller_root / DEFAULT_BUILD_DIRNAME

                if build_path.exists():
                    shutil.rmtree(build_path)

                build_path.mkdir(parents=True, exist_ok=True)

                subprocess.run([
                    "arduino-cli", "compile",
                    "--fqbn", fqbn,
                    "--build-path", str(build_path),
                    str(microcontroller_root),
                ], check=True)
                subprocess.run([
                    "arduino-cli", "upload",
                    "-p", port,
                    "--fqbn", fqbn,
                    "--input-dir", str(build_path),
                    str(microcontroller_root),
                ], check=True)
                Flash.record_firmware_digest(board)

        except Exception as e:
            raise RuntimeError(
                "Failed to flash hardware system "
                f"{hardware_plan.hardware_system_id}"
            ) from e

    @staticmethod
    def flash(hardware: HardwareSystem | HardwarePlan) -> None:
        Flash.flash_code(hardware)

    @staticmethod
    def flash_all(hardware: HardwareSystem | HardwarePlan) -> None:
        Flash.flash_all_code(hardware)

    @staticmethod
    def manifest_path(board: ResolvedBoard) -> Path:
        return FIRMWARE_PATH / board.microcontroller_id / "installed.json"

    @staticmethod
    def firmware_is_current(board: ResolvedBoard) -> bool:
        manifest_path = Flash.manifest_path(board)
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        return manifest.get("contract_digest") == board.contract_digest

    @staticmethod
    def record_firmware_digest(board: ResolvedBoard) -> None:
        Flash.manifest_path(board).write_text(
            json.dumps(
                {"contract_digest": board.contract_digest},
                indent=2,
            )
        )

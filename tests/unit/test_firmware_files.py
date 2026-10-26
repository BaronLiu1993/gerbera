from pathlib import Path
import subprocess

import pytest

from gerbera_sdk.firmware.firmware_compiler import FirmwareCompiler
from gerbera_sdk.firmware.firmware_uploader import FirmwareUploader
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.firmware.firmware_generator import (
    FirmwareFiles,
    FirmwareGenerator,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
    RuntimeTransportConfig,
    RuntimeWatchdogConfig,
)


def test_generated_firmware_is_stored_in_gerbera(
    tmp_path,
    monkeypatch,
    device_registry,
) -> None:
    device_registry({"board-1": "/dev/board-1"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        FirmwareGenerator,
        "generate",
        lambda self: FirmwareFiles(
            sketch="// sketch",
            runtime_header="// runtime header",
            runtime_source="// runtime source",
            components_header="// components header",
            components_source="// components source",
            commands_header="// commands header",
            commands_source="// commands source",
        ),
    )
    board = Microcontroller(
        device_id="board-1",
        name="board",
        port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
    )
    hardware_system = HardwareSystem(
        name="test",
        microcontrollers=[board],
    )
    board.hardware_system_id = hardware_system.id

    sketch_path = FirmwareGenerator(board).write_files()

    expected_path = Path(".gerbera/firmware/board-1/board-1.ino")
    assert sketch_path == expected_path
    assert expected_path.read_text() == "// sketch"
    assert (expected_path.parent / "GerberaRuntime.h").is_file()
    assert (expected_path.parent / "GerberaRuntime.cpp").is_file()
    assert (expected_path.parent / "Components.h").is_file()
    assert (expected_path.parent / "Components.cpp").is_file()
    assert (expected_path.parent / "DeviceCommands.h").is_file()
    assert (expected_path.parent / "DeviceCommands.cpp").is_file()


def make_bluetooth_hardware() -> HardwareSystem:
    board = Microcontroller(
        name="esp32",
        port="/dev/legacy-port",
        upload_port="/dev/usb-esp32",
        device_id="esp32-1",
        runtime_transport=RuntimeTransportConfig.bluetooth_classic(
            "/dev/bluetooth-esp32",
            "Gerbera-ESP32",
        ),
        fqbn="esp32:esp32:esp32",
        watchdog=RuntimeWatchdogConfig(500, 2500),
    )
    hardware = HardwareSystem(name="esp32", microcontrollers=[board])
    board.hardware_system_id = hardware.id
    return hardware


@pytest.fixture
def firmware_board():
    return HardwareContractCompiler.compile(make_bluetooth_hardware()).boards[0]


def test_compiler_only_compiles_generated_source(tmp_path, monkeypatch, firmware_board) -> None:
    sketch_path = tmp_path / "board.ino"
    sketch_path.write_text("void setup() {} void loop() {}")
    commands = []
    monkeypatch.setattr(
        "gerbera_sdk.firmware.firmware_compiler.subprocess.run",
        lambda command, check: commands.append(command),
    )

    build_path = FirmwareCompiler(firmware_board).compile(sketch_path)

    assert commands == [[
        "arduino-cli", "compile", "--fqbn", firmware_board.fqbn,
        "--build-path", str(build_path), str(tmp_path),
    ]]


def test_compiler_requires_generated_source(tmp_path, firmware_board) -> None:
    with pytest.raises(FileNotFoundError, match="sketch not found"):
        FirmwareCompiler(firmware_board).compile(tmp_path / "missing.ino")


def test_compiler_propagates_build_failure(tmp_path, monkeypatch, firmware_board) -> None:
    sketch_path = tmp_path / "board.ino"
    sketch_path.touch()

    def fail_compile(command, check):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("gerbera_sdk.firmware.firmware_compiler.subprocess.run", fail_compile)

    with pytest.raises(subprocess.CalledProcessError):
        FirmwareCompiler(firmware_board).compile(sketch_path)


def test_uploader_only_uploads_existing_build_through_usb(tmp_path, monkeypatch, firmware_board) -> None:
    build_path = tmp_path / "build"
    build_path.mkdir()
    commands = []
    monkeypatch.setattr(
        "gerbera_sdk.firmware.firmware_uploader.subprocess.run",
        lambda command, check: commands.append(command),
    )

    FirmwareUploader(firmware_board).upload(build_path)

    assert commands == [[
        "arduino-cli", "upload", "-p", "/dev/usb-esp32",
        "--fqbn", firmware_board.fqbn, "--input-dir", str(build_path), str(tmp_path),
    ]]


def test_uploader_requires_existing_build(tmp_path, firmware_board) -> None:
    with pytest.raises(FileNotFoundError, match="directory not found"):
        FirmwareUploader(firmware_board).upload(tmp_path / "missing")


def test_uploader_propagates_upload_failure(tmp_path, monkeypatch, firmware_board) -> None:
    def fail_upload(command, check):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("gerbera_sdk.firmware.firmware_uploader.subprocess.run", fail_upload)

    with pytest.raises(subprocess.CalledProcessError):
        FirmwareUploader(firmware_board).upload(tmp_path)

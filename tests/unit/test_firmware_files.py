from pathlib import Path
import subprocess

import pytest

from gerbera_sdk.firmware.flash import Flash
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

    sketch_paths = Flash.generate_files(hardware_system)

    expected_path = Path(".gerbera/firmware/board-1/board-1.ino")
    assert sketch_paths == {"board-1": expected_path}
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


def test_flash_uploads_through_the_usb_port(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "gerbera_sdk.firmware.flash.subprocess.run",
        lambda command, check: commands.append(command),
    )

    Flash.flash_all(make_bluetooth_hardware())

    upload_command = commands[1]
    assert upload_command[upload_command.index("-p") + 1] == "/dev/usb-esp32"


def test_flash_skips_a_current_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "gerbera_sdk.firmware.flash.subprocess.run",
        lambda command, check: commands.append(command),
    )
    hardware = make_bluetooth_hardware()
    Flash.flash_all(hardware)
    commands.clear()

    Flash.flash(hardware)

    assert commands == []


def test_failed_upload_does_not_record_firmware_digest(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    command_count = 0

    def run_command(command, check):
        nonlocal command_count
        command_count += 1
        if command_count == 2:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(
        "gerbera_sdk.firmware.flash.subprocess.run",
        run_command,
    )
    hardware = make_bluetooth_hardware()

    with pytest.raises(RuntimeError):
        Flash.flash_all(hardware)

    assert not Path(
        ".gerbera/firmware/esp32-1/installed.json"
    ).exists()

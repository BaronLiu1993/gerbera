from pathlib import Path
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.firmware.firmware_generator import (
    FirmwareFiles,
    FirmwareGenerator,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    Microcontroller,
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

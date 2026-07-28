from pathlib import Path
from types import SimpleNamespace

from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.firmware.generator import Generator


def test_generated_firmware_is_stored_in_gerbera(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        Generator,
        "build_firmware",
        lambda microcontroller: "// generated firmware",
    )
    hardware_system = SimpleNamespace(
        microcontrollers=[SimpleNamespace(id="board-1")]
    )

    sketch_paths = Flash.generate_files(hardware_system)

    expected_path = Path(".gerbera/firmware/board-1/board-1.ino")
    assert sketch_paths == {"board-1": expected_path}
    assert expected_path.read_text() == "// generated firmware"

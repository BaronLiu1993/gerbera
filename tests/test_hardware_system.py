from gerbera_sdk import Connection, HardwareSystem, Microcontroller


def test_add_microcontroller_rejects_duplicate_ids() -> None:
    hardware_system = HardwareSystem()

    assert hardware_system.add_microcontroller(Microcontroller(id="board-1")) is True
    assert hardware_system.add_microcontroller(Microcontroller(id="board-1")) is False


def test_generate_sketches_writes_one_sketch_per_microcontroller(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  },
  "board-2": {
    "id": "board-2",
    "port": "/dev/cu.usbserial-2140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    first_board = Microcontroller(
        id="board-1",
        baud_rate=115200,
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="First temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )
    second_board = Microcontroller(
        id="board-2",
        baud_rate=9600,
        connections=[
            Connection(
                microcontroller_id="board-2",
                name="greenhouse_temperature",
                description="Second temperature sensor.",
                pins={"signal": "A1"},
                component_type="hw-201",
            )
        ],
    )

    hardware_system = HardwareSystem(microcontrollers=[first_board, second_board])
    sketch_paths = hardware_system.generate_sketches(tmp_path / "build")

    assert set(sketch_paths.keys()) == {"board-1", "board-2"}
    assert sketch_paths["board-1"].name == "board-1.ino"
    assert sketch_paths["board-2"].name == "board-2.ino"
    assert "const int BAUD_RATE = 115200;" in sketch_paths["board-1"].read_text()
    assert "const int BAUD_RATE = 9600;" in sketch_paths["board-2"].read_text()


def test_flash_microcontrollers_requires_fqbn_for_each_board(tmp_path) -> None:
    hardware_system = HardwareSystem(microcontrollers=[Microcontroller(id="board-1")])

    try:
        hardware_system.flash_microcontrollers({}, tmp_path / "build")
    except ValueError as exc:
        assert str(exc) == "Missing fqbn for microcontroller: board-1"
    else:
        raise AssertionError("Expected missing fqbn error")

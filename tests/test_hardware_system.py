from gerbera_sdk import Connection, HardwareSystem, Microcontroller


def test_add_microcontroller_rejects_duplicate_ids() -> None:
    hardware_system = HardwareSystem()

    assert hardware_system.add_microcontroller(Microcontroller(id="board-1")) is True
    assert hardware_system.add_microcontroller(Microcontroller(id="board-1")) is False


def test_get_microcontroller_returns_existing_board() -> None:
    hardware_system = HardwareSystem(
        microcontrollers=[Microcontroller(id="board-1")]
    )

    assert hardware_system.get_microcontroller("board-1").id == "board-1"


def test_generate_sketches_uses_default_user_firmware_folder(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)
    monkeypatch.chdir(tmp_path)

    hardware_system = HardwareSystem(
        microcontrollers=[
            Microcontroller(
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
        ]
    )

    sketch_paths = hardware_system.generate_sketches()

    assert sketch_paths["board-1"] == tmp_path / "gerbera_firmware" / "board-1.ino"
    assert sketch_paths["board-1"].exists()


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


def test_compile_returns_firmware_and_sketch_path(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    controller = Microcontroller(
        id="board-1",
        baud_rate=115200,
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="Temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )
    hardware_system = HardwareSystem(microcontrollers=[controller])

    compiled = hardware_system.compile(tmp_path / "build")

    assert compiled["board-1"]["sketch_path"].name == "board-1.ino"
    assert "handle_room_temperature();" in compiled["board-1"]["firmware"]


def test_build_read_command_delegates_to_microcontroller() -> None:
    controller = Microcontroller(
        id="board-1",
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="Temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )
    hardware_system = HardwareSystem(microcontrollers=[controller])

    assert (
        hardware_system.build_read_command("board-1", "room_temperature")
        == "room_temperature"
    )


def test_prepare_command_returns_transport_metadata(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)"
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    controller = Microcontroller(
        id="board-1",
        baud_rate=115200,
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="Temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )
    hardware_system = HardwareSystem(microcontrollers=[controller])

    result = hardware_system.prepare_command("board-1", "room_temperature")

    assert result == {
        "microcontroller_id": "board-1",
        "connection_name": "room_temperature",
        "port": "/dev/cu.usbserial-1140",
        "protocol": "serial",
        "protocol_label": "Serial Port (USB)",
        "baud_rate": 115200,
        "command": "room_temperature",
    }


def test_parse_response_delegates_to_runtime() -> None:
    hardware_system = HardwareSystem()

    assert hardware_system.parse_response("value:22.5,unit:celsius") == {
        "value": 22.5,
        "unit": "celsius",
    }


def test_flash_microcontrollers_requires_fqbn_for_each_board(tmp_path) -> None:
    hardware_system = HardwareSystem(microcontrollers=[Microcontroller(id="board-1")])

    try:
        hardware_system.flash_microcontrollers({}, tmp_path / "build")
    except ValueError as exc:
        assert str(exc) == "Missing fqbn for microcontroller: board-1"
    else:
        raise AssertionError("Expected missing fqbn error")

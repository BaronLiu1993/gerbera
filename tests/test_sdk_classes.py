from gerbera_sdk import Connection, Microcontroller


def test_microcontroller_serializes_to_output_json_shape(tmp_path, monkeypatch) -> None:
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
        description="Kitchen controller.",
        baud_rate=115200,
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="HW-201 temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )

    assert controller.to_dict() == {
        "id": "board-1",
        "description": "Kitchen controller.",
        "port": "/dev/cu.usbserial-1140",
        "protocol": "serial",
        "protocol_label": "Serial Port (USB)",
        "baud_rate": 115200,
        "connections": [
            {
                "microcontroller_id": "board-1",
                "name": "room_temperature",
                "description": "HW-201 temperature sensor.",
                "pins": {"signal": "A0"},
                "component_type": "hw-201",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                    "required": ["value", "unit"],
                },
            }
        ],
    }


def test_microcontroller_deserializes_from_input_json_shape() -> None:
    payload = {
        "id": "board-1",
        "description": "Kitchen controller.",
        "port": "/dev/cu.usbserial-1140",
        "protocol": "serial",
        "protocol_label": "Serial Port (USB)",
        "baud_rate": 115200,
        "connections": [
            {
                "microcontroller_id": "board-1",
                "name": "room_temperature",
                "description": "HW-201 temperature sensor.",
                "pins": {"signal": "A0"},
                "component_type": "hw-201",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                    "required": ["value", "unit"],
                },
            }
        ],
    }

    controller = Microcontroller.from_dict(payload)

    assert controller.id == "board-1"
    assert controller.description == "Kitchen controller."
    assert controller.baud_rate == 115200
    assert controller.connections[0].name == "room_temperature"
    assert controller.connections[0].pins["signal"] == "A0"
    assert controller.connections[0].component_type == "hw-201"


def test_add_connection_rejects_duplicate_pin_usage(tmp_path, monkeypatch) -> None:
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
    )
    controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="room_temperature",
            description="HW-201 temperature sensor.",
            pins={"signal": "A0"},
            component_type="hw-201",
        )
    )

    added = controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="other_temperature",
            description="Another sensor on the same pin.",
            pins={"signal": "A0"},
            component_type="hw-201",
        )
    )

    assert added is False


def test_add_connection_rejects_duplicate_connection_name_per_board(tmp_path, monkeypatch) -> None:
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

    controller = Microcontroller(id="board-1")
    controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="room_temperature",
            description="HW-201 temperature sensor.",
            pins={"signal": "A0"},
            component_type="hw-201",
        )
    )

    added = controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="room_temperature",
            description="Same command name on another signal pin.",
            pins={"signal": "A1"},
            component_type="hw-201",
        )
    )

    assert added is False


def test_get_board_information_uses_device_registry(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "devices.json"
    registry_path.write_text(
        """
{
  "board-1": {
    "id": "board-1",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)",
    "baud_rate": 115200
  }
}
""".strip()
    )
    monkeypatch.setattr("gerbera_sdk.hardware.microcontroller.DEVICE_REGISTRY_PATH", registry_path)

    controller = Microcontroller(id="board-1")

    assert controller.get_board_information() == {
        "port": "/dev/cu.usbserial-1140",
        "protocol": "serial",
        "protocol_label": "Serial Port (USB)",
    }


def test_add_connection_raises_for_missing_required_pin_role(tmp_path, monkeypatch) -> None:
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

    controller = Microcontroller(id="board-1")

    try:
        controller.add_connection(
            Connection(
                microcontroller_id="board-1",
                name="room_temperature",
                description="HW-201 temperature sensor.",
                pins={},
                component_type="hw-201",
            )
        )
    except ValueError as exc:
        assert str(exc) == "Missing required pins for hw-201: signal"
    else:
        raise AssertionError("Expected missing required pins error")

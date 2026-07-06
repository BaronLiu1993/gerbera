from gerbera_sdk import Connection, Microcontroller, Pin


def test_microcontroller_serializes_to_output_json_shape(tmp_path, monkeypatch) -> None:
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

    controller = Microcontroller(
        id="board-1",
        description="Kitchen controller.",
        connections=[
            Connection(
                microcontroller_id="board-1",
                name="status_led",
                description="Status LED on the board.",
                pins=[Pin(pin_val="13")],
                component_type="led",
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
                "name": "status_led",
                "description": "Status LED on the board.",
                "pins": [
                    {
                        "pin": "13",
                    }
                ],
                "component_type": "led",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "boolean"},
                    }
                    ,
                    "required": ["value"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
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
                "name": "status_led",
                "description": "Status LED on the board.",
                "pins": [{"pin": "13"}],
                "component_type": "led",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "boolean"},
                    },
                    "required": ["value"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }
        ],
    }

    controller = Microcontroller.from_dict(payload)

    assert controller.id == "board-1"
    assert controller.description == "Kitchen controller."
    assert controller.connections[0].name == "status_led"
    assert controller.connections[0].pins[0].pin_val == "13"
    assert controller.connections[0].component_type == "led"


def test_add_connection_rejects_duplicate_pin_usage(tmp_path, monkeypatch) -> None:
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

    controller = Microcontroller(
        id="board-1",
    )
    controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="status_led",
            description="Status LED on the board.",
            pins=[Pin(pin_val="13")],
            component_type="led",
        )
    )

    added = controller.add_connection(
        Connection(
            microcontroller_id="board-1",
            name="other_led",
            description="Another LED on the same pin.",
            pins=[Pin(pin_val="13")],
            component_type="led",
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

    assert controller._get_board_information() == {
        "port": "/dev/cu.usbserial-1140",
        "protocol": "serial",
        "protocol_label": "Serial Port (USB)",
        "baud_rate": 115200,
    }

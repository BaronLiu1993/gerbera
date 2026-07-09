from gerbera_sdk import Connection, FirmwareGenerator, Microcontroller


def test_hw_201_firmware_generation_uses_read_dispatch_and_signal_pin(tmp_path, monkeypatch) -> None:
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
                description="HW-201 temperature sensor.",
                pins={"signal": "A0"},
                component_type="hw-201",
            )
        ],
    )

    sketch = FirmwareGenerator.generate(controller)

    assert "#include <Arduino.h>" in sketch
    assert "pinMode(A0, INPUT);" in sketch
    assert "String firstToken(String input)" in sketch
    assert "String parameterValue(String input, String parameterName)" in sketch
    assert "String commandName = firstToken(line);" in sketch
    assert 'if (commandName == "room_temperature")' in sketch
    assert "handle_room_temperature();" in sketch
    assert "analogRead(A0)" in sketch
    assert 'Serial.println(",unit:celsius");' in sketch

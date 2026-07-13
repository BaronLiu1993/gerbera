from gerbera_sdk import Connection
from gerbera_sdk.contracts.firmware_contract import ColumnType, PinMode
from gerbera_sdk.firmware.devices.hcsr04 import HCSR04FirmwareBuilder


def test_hcsr04_builder_defines_pins_command_and_handler() -> None:
    connection = Connection(
        id="distance-sensor",
        microcontroller_id="board-1",
        name="distance_sensor",
        component_type="hcsr04",
        pins={
            "trig": "8",
            "echo": "9",
        },
    )
    builder = HCSR04FirmwareBuilder()

    pin_modes = builder.pin_modes(connection)
    commands = builder.required_commands(connection)
    handler = builder.build_handler(connection)

    assert pin_modes[0].pin == "8"
    assert pin_modes[0].mode == PinMode.OUTPUT
    assert pin_modes[1].pin == "9"
    assert pin_modes[1].mode == PinMode.INPUT
    assert [command.method for command in commands] == ["READ"]
    assert "pulseIn(9, HIGH, 30000)" in handler
    assert "MCP,hcsr04_fbc1de23_b67cc64a,distance_cm:" in handler


def test_hcsr04_builder_supports_database_streaming() -> None:
    connection = Connection(
        id="distance-sensor",
        microcontroller_id="board-1",
        name="distance_sensor",
        component_type="hcsr04",
        pins={
            "trig": "8",
            "echo": "9",
        },
        database=object(),
    )
    builder = HCSR04FirmwareBuilder()

    commands = builder.required_commands(connection)
    schema = builder.required_schema(connection)
    definitions = builder.build_definitions(connection)
    stream_lines = "\n".join(builder.build_stream_lines(connection))
    handler = builder.build_handler(connection)

    assert [command.method for command in commands] == ["READ", "WRITE"]
    assert commands[1].params["state"].enum == ["on", "off"]
    assert schema["distance_cm"].type == ColumnType.FLOAT
    assert "bool distance_sensor_stream_on = false;" in definitions
    assert "if (distance_sensor_stream_on)" in stream_lines
    assert "STREAM,hcsr04_fbc1de23_b67cc64a,distance_cm:" in stream_lines
    assert 'if (action == "WRITE")' in handler
    assert "distance_sensor_stream_on = true;" in handler
    assert "distance_sensor_stream_on = false;" in handler

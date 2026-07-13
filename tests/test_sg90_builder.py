from gerbera_sdk import Connection
from gerbera_sdk.contracts.command_contract import ParameterType
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


def test_sg90_builder_servo_contract() -> None:
    connection = Connection(
        id="servo-motor",
        microcontroller_id="board-1",
        name="servo_motor",
        component_type="sg90",
        pins={"signal": "10"},
    )
    builder = SG90FirmwareBuilder()

    libraries = builder.required_libraries()
    commands = builder.required_commands(connection)
    handler = builder.build_handler(connection)

    assert libraries[0].include == "Servo.h"
    assert libraries[0].install == "Servo"
    assert builder.pin_modes(connection) == []
    assert commands[0].method == "WRITE"
    assert commands[0].params["angle"].type == ParameterType.INT
    assert commands[0].params["angle"].required is True
    assert commands[0].params["angle"].min == 0
    assert commands[0].params["angle"].max == 180
    assert "Servo servo_motor_servo;" in builder.build_definitions(connection)
    assert builder.build_setup_lines(connection) == ["  servo_motor_servo.attach(10);"]
    assert 'parameterValue(input, "angle")' in handler
    assert "servo_motor_servo.write(angle);" in handler
    assert "MCP,sg90_servo-motor,angle:" in handler
    assert "MCP,sg90_servo-motor,error:invalid_arg" in handler

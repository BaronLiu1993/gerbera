from gerbera_sdk import Connection
from gerbera_sdk.contracts.firmware_contract import PinMode
from gerbera_sdk.firmware.devices.dcmotor import DCMotorFirmwareBuilder
import pytest


def test_dcmotor_builder_defines_write_only_driver_contract() -> None:
    connection = Connection(
        id="drive-motor",
        microcontroller_id="board-1",
        name="drive_motor",
        component_type="dcmotor",
        pins={
            "in1": "5",
            "in2": "6",
            "enable": "9",
        },
    )
    builder = DCMotorFirmwareBuilder()

    pin_modes = builder.pin_modes(connection)
    commands = builder.required_commands(connection)
    handler = builder.build_handler(connection)

    assert [(pin.pin, pin.mode) for pin in pin_modes] == [
        ("5", PinMode.OUTPUT),
        ("6", PinMode.OUTPUT),
        ("9", PinMode.OUTPUT),
    ]
    assert [command.method for command in commands] == ["WRITE"]
    assert commands[0].params["direction"].enum == ["forward", "reverse", "stop"]
    assert commands[0].params["speed"].min == 0
    assert commands[0].params["speed"].max == 255
    assert "digitalWrite(5, HIGH);" in handler
    assert "digitalWrite(6, HIGH);" in handler
    assert "analogWrite(9, speed);" in handler
    assert "analogWrite(9, 0);" in handler
    assert "MCP,dcmotor_fbc1de23_67b5a2fa,status:forward" in handler
    assert "MCP,dcmotor_fbc1de23_67b5a2fa,status:reverse" in handler
    assert "MCP,dcmotor_fbc1de23_67b5a2fa,status:stop" in handler
    assert "MCP,dcmotor_fbc1de23_67b5a2fa,error:invalid_direction" in handler


def test_dcmotor_builder_requires_enable_pin_for_pwm() -> None:
    connection = Connection(
        id="drive-motor",
        microcontroller_id="board-1",
        name="drive_motor",
        component_type="dcmotor",
        pins={
            "in1": "5",
            "in2": "6",
        },
    )
    builder = DCMotorFirmwareBuilder()

    with pytest.raises(KeyError):
        builder.pin_modes(connection)

    with pytest.raises(KeyError):
        builder.build_handler(connection)

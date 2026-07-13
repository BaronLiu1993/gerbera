from gerbera_sdk import Connection
from gerbera_sdk.contracts.command_contract import ParameterType
from gerbera_sdk.contracts.firmware_contract import PinMode
from gerbera_sdk.firmware.devices.led import LEDFirmwareBuilder


def test_led_builder_write_contract_and_handler() -> None:
    connection = Connection(
        id="green-led",
        microcontroller_id="board-1",
        name="green_led",
        component_type="led",
        pins={"out": "13"},
    )
    builder = LEDFirmwareBuilder()

    pin_modes = builder.pin_modes(connection)
    commands = builder.required_commands(connection)
    handler = builder.build_handler(connection)

    assert [(pin.pin, pin.mode) for pin in pin_modes] == [("13", PinMode.OUTPUT)]
    assert [command.method for command in commands] == ["WRITE"]
    assert commands[0].params["state"].type == ParameterType.STRING
    assert commands[0].params["state"].required is True
    assert commands[0].params["state"].enum == ["on", "off"]
    assert 'parameterValue(input, "state")' in handler
    assert "digitalWrite(13, HIGH);" in handler
    assert "digitalWrite(13, LOW);" in handler
    assert "MCP,led_fbc1de23_f928a260,state:on" in handler
    assert "MCP,led_fbc1de23_f928a260,state:off" in handler
    assert "MCP,led_fbc1de23_f928a260,error:invalid_arg" in handler
    assert "MCP,led_fbc1de23_f928a260,error:invalid_value" in handler

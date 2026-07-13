from gerbera_sdk import Connection
from gerbera_sdk.firmware.devices.mg996r import MG996RFirmwareBuilder
from gerbera_sdk.firmware.devices.sg90 import SG90FirmwareBuilder


def test_mg996r_builder_reuses_servo_contract() -> None:
    connection = Connection(
        id="heavy-servo",
        microcontroller_id="board-1",
        name="heavy_servo",
        component_type="mg996r",
        pins={"signal": "10"},
    )
    builder = MG996RFirmwareBuilder()

    assert isinstance(builder, SG90FirmwareBuilder)
    assert builder.template_name == "mg996r_write"
    assert builder.required_libraries()[0].include == "Servo.h"
    assert builder.required_commands(connection)[0].params["angle"].max == 180
    assert "Servo heavy_servo_servo;" in builder.build_definitions(connection)
    assert builder.build_setup_lines(connection) == ["  heavy_servo_servo.attach(10);"]
    handler = builder.build_handler(connection)
    assert "heavy_servo_servo.write(angle);" in handler
    assert "MCP,mg996r_fbc1de23_ed45b427,angle:" in handler

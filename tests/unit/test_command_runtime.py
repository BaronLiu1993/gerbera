import pytest

from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler


def _connection(component_type: str) -> Connection:
    pins = {
        "led": {"out": "13"},
        "sg90": {"signal": "10"},
    }
    return Connection(
        name="component",
        component_type=component_type,
        pins=pins[component_type],
        microcontroller_id="board-1",
    )


def test_build_command_normalizes_a_valid_parameter() -> None:
    command = CommandCompiler.build_command(
        _connection("led"),
        " write ",
        {"state": "on"},
    )

    assert command == "WRITE,component,state:on"


@pytest.mark.parametrize(
    ("connection", "params", "message"),
    [
        (_connection("led"), None, "Missing required parameter"),
        (_connection("led"), {"state": "invalid"}, "Unsupported value"),
        (_connection("led"), {"unknown": "on"}, "Unsupported parameter"),
        (_connection("sg90"), {"angle": "181"}, "must be <= 180"),
        (_connection("sg90"), {"angle": "not-an-int"}, "Invalid int value"),
    ],
)
def test_build_command_rejects_invalid_parameters(
    connection: Connection,
    params: dict[str, str] | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CommandCompiler.build_command(connection, "WRITE", params)


def test_build_command_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unsupported command"):
        CommandCompiler.build_command(_connection("sg90"), "READ")


@pytest.mark.parametrize("component_type", sorted(DEVICES_MAPPING))
def test_every_device_command_defines_complete_tool_annotations(
    component_type: str,
) -> None:
    pins = {
        "dcmotor": {"in1": "1", "in2": "2", "enable": "3"},
        "hcsr04": {"trig": "4", "echo": "5"},
        "hw201": {"out": "6"},
        "ky033": {"out": "7"},
        "led": {"out": "8"},
        "mg996r": {"signal": "9"},
        "sg90": {"signal": "10"},
    }
    connection = Connection(
        name=f"test_{component_type}",
        component_type=component_type,
        pins=pins[component_type],
        database=Database(
            "localhost",
            5432,
            "user",
            "password",
            "gerbera",
        ),
    )

    commands = CommandCompiler.command_specs(connection)

    assert commands
    for command in commands:
        annotations = CommandCompiler.command_annotations(
            connection,
            command,
        )
        assert annotations.title
        assert annotations.readOnlyHint is not None
        assert annotations.destructiveHint is not None
        assert annotations.idempotentHint is not None
        assert annotations.openWorldHint is not None

import pytest

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

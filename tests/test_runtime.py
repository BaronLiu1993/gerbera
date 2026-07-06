from gerbera_sdk import ConnectionRuntime


def test_build_read_command_uses_action_first_shape() -> None:
    class FakeConnection:
        name = "room_temperature"

    assert ConnectionRuntime.build_read_command(FakeConnection()) == "room_temperature"


def test_build_command_serializes_typed_params() -> None:
    class FakeConnection:
        name = "set_led"

    assert ConnectionRuntime.build_command(
        FakeConnection(),
        {"value": ("bool", "true"), "duration": ("int", 5)},
    ) == "set_led,value:bool:true,duration:int:5"


def test_parse_response_returns_typed_payload() -> None:
    assert ConnectionRuntime.parse_response("value:23.5,unit:celsius") == {
        "value": 23.5,
        "unit": "celsius",
    }

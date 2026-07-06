import pytest

from gerbera_sdk.hardware.pin_factory import PinFactory


def test_led_schema_profile_is_write_like() -> None:
    assert PinFactory.build("led") == {
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


def test_button_schema_profile_is_read_like() -> None:
    assert PinFactory.build("button") == {
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "pressed": {"type": "boolean"},
            },
            "required": ["pressed"],
        },
    }


def test_unknown_component_type_raises_error() -> None:
    with pytest.raises(ValueError, match="Unsupported component type: unknown_component"):
        PinFactory.build("unknown_component")

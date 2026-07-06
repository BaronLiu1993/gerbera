import pytest

from gerbera_sdk.hardware.pin_factory import PinFactory


def test_led_schema_profile_is_write_like() -> None:
    assert PinFactory.build("  LED  ") == {
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "boolean"},
            },
            "required": ["value"],
        },
    }


def test_button_schema_profile_is_read_like() -> None:
    assert PinFactory.build("button") == {
        "outputSchema": {
            "type": "object",
            "properties": {
                "pressed": {"type": "boolean"},
            },
            "required": ["pressed"],
        },
    }


def test_hw_201_schema_profile_uses_normalized_name_lookup() -> None:
    assert PinFactory.build(" hw-201 ") == {
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string"},
            },
            "required": ["value", "unit"],
        },
    }


def test_unknown_component_type_raises_error() -> None:
    with pytest.raises(ValueError, match="Unsupported component type: unknown_component"):
        PinFactory.build("unknown_component")

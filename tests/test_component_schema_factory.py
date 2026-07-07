import pytest

from gerbera_sdk.components.registry import ComponentRegistry
from gerbera_sdk.hardware.pin import PinFactory


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


def test_hw_201_component_profile_exposes_required_pin_role() -> None:
    assert ComponentRegistry.get("hw-201")["pins"] == ["signal"]


def test_unknown_component_type_raises_error() -> None:
    with pytest.raises(ValueError, match="Unsupported component type: unknown_component"):
        PinFactory.build("unknown_component")

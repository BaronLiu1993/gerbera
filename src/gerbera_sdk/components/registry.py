import json
from pathlib import Path
from typing import Any


COMPONENT_SCHEMA_PROFILES_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "component_schema_profiles.json"
)


class ComponentRegistry:
    @staticmethod
    def get(component_type: str) -> dict[str, Any]:
        normalized_component_type = ComponentRegistry._normalize_component_type(component_type)
        profiles = ComponentRegistry._load_profiles()

        if normalized_component_type not in profiles:
            raise ValueError(f"Unsupported component type: {component_type}")

        return profiles[normalized_component_type]

    @staticmethod
    def validate_pins(component_type: str, pins: dict[str, str]) -> None:
        profile = ComponentRegistry.get(component_type)
        required_pins = [str(pin_name) for pin_name in profile.get("pins", [])]
        missing_pins = [pin_name for pin_name in required_pins if pin_name not in pins]

        if missing_pins:
            missing_pin_list = ", ".join(missing_pins)
            raise ValueError(
                f"Missing required pins for {component_type}: {missing_pin_list}"
            )

    @staticmethod
    def _load_profiles() -> dict[str, dict[str, Any]]:
        payload = json.loads(COMPONENT_SCHEMA_PROFILES_PATH.read_text())
        return {
            ComponentRegistry._normalize_component_type(component_name): profile
            for component_name, profile in payload.items()
        }

    @staticmethod
    def _normalize_component_type(component_type: str) -> str:
        return component_type.strip().lower()

import json
from pathlib import Path
from typing import Any


COMPONENT_SCHEMA_PROFILES_PATH = (
    Path(__file__).resolve().parent.parent / "component_schema_profiles.json"
)


class PinFactory:
    @staticmethod
    def build(
        component_type: str,
    ) -> dict[str, Any]:
        normalized_component_type = PinFactory._normalize_component_type(component_type)
        component_schema_profiles = PinFactory._load_component_schema_profiles()

        if normalized_component_type not in component_schema_profiles:
            raise ValueError(f"Unsupported component type: {component_type}")

        profile = component_schema_profiles[normalized_component_type]
        input_schema = {
            "type": "object",
            "properties": dict(profile.get("input", {})),
            "required": list(profile.get("input", {}).keys()),
        }
        output_schema = {
            "type": "object",
            "properties": dict(profile.get("output", {})),
            "required": list(profile.get("output", {}).keys()),
        }

        payload: dict[str, Any] = {}

        if input_schema["properties"]:
            payload["inputSchema"] = input_schema

        if output_schema["properties"]:
            payload["outputSchema"] = output_schema

        return payload

    @staticmethod
    def _load_component_schema_profiles() -> dict[str, dict[str, Any]]:
        payload = json.loads(COMPONENT_SCHEMA_PROFILES_PATH.read_text())
        return {
            PinFactory._normalize_component_type(component_name): profile
            for component_name, profile in payload.items()
        }

    @staticmethod
    def _normalize_component_type(component_type: str) -> str:
        return component_type.strip().lower()

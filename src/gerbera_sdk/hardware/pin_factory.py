from typing import Any

from gerbera_sdk.config.component_schema_profiles import COMPONENT_SCHEMA_PROFILES


class PinFactory:
    @staticmethod
    def build(
        component_type: str,
    ) -> dict[str, Any]:
        if component_type not in COMPONENT_SCHEMA_PROFILES:
            raise ValueError(f"Unsupported component type: {component_type}")

        profile = COMPONENT_SCHEMA_PROFILES[component_type]
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

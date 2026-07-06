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
        return {
            "inputSchema": {
                "type": "object",
                "properties": dict(profile.get("input", {})),
                "required": list(profile.get("input", {}).keys()),
            },
            "outputSchema": {
                "type": "object",
                "properties": dict(profile.get("output", {})),
                "required": list(profile.get("output", {}).keys()),
            },
        }

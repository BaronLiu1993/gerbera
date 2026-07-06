from typing import Any

from gerbera_sdk.components.registry import ComponentRegistry


class PinFactory:
    @staticmethod
    def build(
        component_type: str,
    ) -> dict[str, Any]:
        profile = ComponentRegistry.get(component_type)
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

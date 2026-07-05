from typing import Any, Optional


class PinFactory:
    @staticmethod
    def build(
        mode: str,
        input_properties: Optional[dict[str, Any]] = None,
        output_properties: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        input_properties = input_properties or {}
        output_properties = output_properties or {}

        if mode == "read":
            return {
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": output_properties,
                    "required": list(output_properties.keys()),
                },
            }

        if mode == "write":
            return {
                "inputSchema": {
                    "type": "object",
                    "properties": input_properties,
                    "required": list(input_properties.keys()),
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }

        return {
            "inputSchema": {
                "type": "object",
                "properties": input_properties,
                "required": list(input_properties.keys()),
            },
            "outputSchema": {
                "type": "object",
                "properties": output_properties,
                "required": list(output_properties.keys()),
            },
        }

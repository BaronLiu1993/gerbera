from typing import Any


COMPONENT_SCHEMA_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "led": {
        "input": {
            "value": {"type": "boolean"},
        },
        "output": {},
    },
    "button": {
        "input": {},
        "output": {
            "pressed": {"type": "boolean"},
        },
    },
    "temperature_sensor": {
        "input": {},
        "output": {
            "value": {"type": "number"},
            "unit": {"type": "string"},
        },
    },
}

import hashlib
import re


MAX_EVENT_NAME_LENGTH = 63
EventKey = tuple[str, str, str]


def build_event_key(
    event_type: str,
    microcontroller_id: str,
    event_name: str,
) -> EventKey:
    return (event_type, microcontroller_id, event_name)


def build_connection_event_name(
    component_type: str,
    microcontroller_id: str,
    pins: dict[str, str] | None = None,
) -> str:
    microcontroller_hash = hashlib.sha1(
        microcontroller_id.encode()
    ).hexdigest()[:8]
    pin_hash = hashlib.sha1(
        build_pin_signature(pins).encode()
    ).hexdigest()[:8]
    return safe_identifier(f"{component_type}_{microcontroller_hash}_{pin_hash}")


def build_pin_signature(pins: dict[str, str] | None = None) -> str:
    normalized_pins = pins or {}
    return ",".join(
        f"{str(key)}={str(value)}"
        for key, value in sorted(normalized_pins.items())
    )


def safe_identifier(
    value: str,
    max_length: int = MAX_EVENT_NAME_LENGTH,
) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if len(normalized) <= max_length:
        return normalized

    digest = hashlib.sha1(normalized.encode()).hexdigest()[:8]
    prefix_length = max_length - len(digest) - 1
    return f"{normalized[:prefix_length].rstrip('_')}_{digest}"

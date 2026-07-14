import hashlib
import re


MAX_EVENT_NAME_LENGTH = 63


def build_event_key(
    event_type: str,
    microcontroller_id: str,
    event_name: str,
) -> tuple[str, str, str]:
    return (event_type, microcontroller_id, event_name)


def build_connection_event_name(
    component_type: str,
    microcontroller_id: str,
) -> str:
    microcontroller_hash = hashlib.sha1(
        microcontroller_id.encode()
    ).hexdigest()[:8]
    return safe_identifier(f"{component_type}_{microcontroller_hash}")


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

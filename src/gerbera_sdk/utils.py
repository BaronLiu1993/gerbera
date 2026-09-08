import hashlib
import re

from pydantic import BaseModel, ConfigDict

MAX_EVENT_NAME_LENGTH = 63


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def build_event_key(
    event_type: str,
    microcontroller_id: str,
    event_name: str,
) -> str:
    return f"{event_type}.{microcontroller_id}.{event_name}"


def parse_event_key(event_key: str) -> tuple[str, str, str]:
    event_type, remainder = event_key.split(".", 1)
    microcontroller_id, event_name = remainder.rsplit(".", 1)
    return event_type, microcontroller_id, event_name


def hash_event_key(event_key: str) -> str:
    return hashlib.sha256(event_key.encode()).hexdigest()


def build_connection_event_name(
    component_type: str,
    microcontroller_id: str,
    pins: dict[object, object],
) -> str:
    pin_signature = ",".join(
        f"{key}={value}"
        for key, value in sorted((str(key), str(value)) for key, value in pins.items())
    )
    microcontroller_hash = hashlib.sha1(microcontroller_id.encode()).hexdigest()[:8]
    pin_hash = hashlib.sha1(pin_signature.encode()).hexdigest()[:8]
    source = f"{component_type}_{microcontroller_hash}_{pin_hash}"
    return safe_identifier(source)


def safe_identifier(value: str, max_length: int = MAX_EVENT_NAME_LENGTH) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if len(normalized) <= max_length:
        return normalized

    digest = hashlib.sha1(normalized.encode()).hexdigest()[:8]
    prefix = normalized[: max_length - len(digest) - 1].rstrip("_")
    return f"{prefix}_{digest}"

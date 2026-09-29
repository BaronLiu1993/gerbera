import hashlib
import re

from pydantic import BaseModel, ConfigDict

MAX_EVENT_NAME_LENGTH = 63

class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

def build_connection_event_name(
    microcontroller_id: str,
    connection_name: str,
) -> str:
    connection_key = "\0".join(
        (microcontroller_id, connection_name)
    )
    digest = hashlib.sha256(connection_key.encode()).hexdigest()[:16]
    source = f"{connection_name}_{digest}"
    return safe_identifier(source)


def safe_identifier(value: str, max_length: int = MAX_EVENT_NAME_LENGTH) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if len(normalized) <= max_length:
        return normalized

    digest = hashlib.sha1(normalized.encode()).hexdigest()[:8]
    prefix = normalized[: max_length - len(digest) - 1].rstrip("_")
    return f"{prefix}_{digest}"

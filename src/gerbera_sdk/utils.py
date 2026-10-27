import hashlib
import json
import re
from typing import Self

from pydantic import BaseModel, ConfigDict

MAX_EVENT_NAME_LENGTH = 63

class StrictSchema(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", validate_assignment=True, allow_inf_nan=False,
    )

    @classmethod
    def from_data(cls, data: dict[str, object]) -> Self:
        return cls.model_validate_json(json.dumps(data, allow_nan=False))

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

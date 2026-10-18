from typing import Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "1"


class RuntimeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal["1"] = PROTOCOL_VERSION
    instance_id: str
    capabilities: tuple[str, ...]
    resource_uris: tuple[str, ...]

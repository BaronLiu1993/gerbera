from typing import Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "1"


class RuntimeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal["1"] = PROTOCOL_VERSION
    instance_id: str


class ReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal["1"] = PROTOCOL_VERSION
    service: Literal["sdk", "harness"]
    phase: Literal["starting", "ready", "degraded", "failed", "stopping"]
    reasons: tuple[str, ...] = ()
    instance_id: str | None = None

    @property
    def ready(self) -> bool:
        return self.phase == "ready"

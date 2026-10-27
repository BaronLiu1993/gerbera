from dataclasses import dataclass
from typing import Protocol

from gerbera_protocol import ReadinessReport


class ReadinessSource(Protocol):
    def readiness_reasons(self) -> tuple[str, ...]: ...


@dataclass
class RuntimeReadiness:
    sources: tuple[ReadinessSource, ...]
    instance_id: str
    phase: str = "starting"

    def snapshot(self) -> ReadinessReport:
        reasons = [f"SDK is {self.phase}"] if self.phase != "ready" else []
        for source in self.sources:
            reasons.extend(source.readiness_reasons())
        phase = self.phase
        if phase == "ready" and reasons:
            phase = "degraded"
        return ReadinessReport(
            service="sdk", phase=phase, reasons=tuple(reasons), instance_id=self.instance_id,
        )

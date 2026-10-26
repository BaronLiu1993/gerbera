from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import asyncio

from gerbera_protocol import ReadinessReport
from gerbera_harness.runtime.contracts import ToolSource


@dataclass
class HarnessReadiness:
    tools: ToolSource
    dependency_health: Callable[[], Awaitable[ReadinessReport]] | None = None
    phase: str = "starting"
    dependency_timeout_seconds: float = 3

    async def snapshot(self) -> ReadinessReport:
        reasons = []
        if self.phase != "ready":
            reasons.append(f"Harness is {self.phase}")
        if self.phase == "ready":
            try:
                await asyncio.wait_for(self.tools.list_tools(), self.dependency_timeout_seconds)
            except Exception:
                reasons.append("Tool discovery unavailable")
            if self.dependency_health is not None:
                try:
                    report = await asyncio.wait_for(self.dependency_health(), self.dependency_timeout_seconds)
                    if not report.ready:
                        reasons.append("Configured SDK is not ready")
                except Exception:
                    reasons.append("Configured SDK readiness unavailable")
        return ReadinessReport(
            service="harness", reasons=tuple(reasons),
            phase=self.phase if self.phase != "ready" else ("degraded" if reasons else "ready"),
        )

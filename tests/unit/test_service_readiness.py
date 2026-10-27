import asyncio
from types import SimpleNamespace

import pytest
import httpx
from starlette.applications import Starlette

from gerbera_harness.api.readiness import install_readiness
from gerbera_harness.runtime.readiness import HarnessReadiness
from gerbera_protocol import ReadinessReport
from gerbera_sdk.models.runtime.server.readiness import RuntimeReadiness


@pytest.fixture
def sdk_readiness():
    sources = tuple(SimpleNamespace(readiness_reasons=lambda: ()) for _ in range(5))
    return RuntimeReadiness(sources=sources, instance_id="robot", phase="ready")


def test_sdk_reports_ready_only_after_all_dependencies_started(sdk_readiness) -> None:
    assert sdk_readiness.snapshot().model_dump() == {
        "protocol_version": "1", "service": "sdk",
        "phase": "ready", "reasons": (), "instance_id": "robot",
    }


@pytest.mark.parametrize("phase, expected_ready", [("starting", False), ("ready", True), ("degraded", False)])
def test_readiness_is_derived_from_phase(phase, expected_ready) -> None:
    report = ReadinessReport(service="sdk", phase=phase)

    assert report.ready is expected_ready


def test_sdk_lifecycle_phase_controls_readiness(sdk_readiness) -> None:
    sdk_readiness.phase = "starting"

    report = sdk_readiness.snapshot()

    assert (report.ready, report.phase, report.reasons) == (False, "starting", ("SDK is starting",))


def test_sdk_readiness_collects_all_owner_reports() -> None:
    sources = (
        SimpleNamespace(readiness_reasons=lambda: ("Board unavailable",)),
        SimpleNamespace(readiness_reasons=lambda: ()),
        SimpleNamespace(readiness_reasons=lambda: ("Camera unavailable",)),
    )

    report = RuntimeReadiness(sources, "robot", phase="ready").snapshot()

    assert (report.ready, report.phase, report.reasons) == (
        False, "degraded", ("Board unavailable", "Camera unavailable"),
    )


class Tools:
    async def list_tools(self):
        return []


def test_harness_readiness_follows_remote_sdk_readiness() -> None:
    async def dependency():
        return ReadinessReport(service="sdk", phase="degraded")

    report = asyncio.run(HarnessReadiness(Tools(), dependency, phase="ready").snapshot())

    assert (report.ready, report.reasons) == (False, ("Configured SDK is not ready",))


def test_harness_dependency_errors_are_sanitized() -> None:
    async def dependency():
        raise RuntimeError("password=must-not-leak")

    report = asyncio.run(HarnessReadiness(Tools(), dependency, phase="ready").snapshot())

    assert report.reasons == ("Configured SDK readiness unavailable",)


def test_harness_dependency_readiness_is_bounded() -> None:
    async def dependency():
        await asyncio.Event().wait()

    report = asyncio.run(HarnessReadiness(
        Tools(), dependency, phase="ready", dependency_timeout_seconds=0.01,
    ).snapshot())

    assert report.ready is False


@pytest.mark.parametrize("phase, status", [("starting", 503), ("ready", 200)])
def test_harness_http_readiness_is_distinct_from_liveness(phase, status) -> None:
    app = Starlette()
    install_readiness(app, HarnessReadiness(Tools(), phase=phase))

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://harness") as client:
            return (await client.get("/ready")).status_code

    assert asyncio.run(scenario()) == status

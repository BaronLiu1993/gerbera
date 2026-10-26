import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from gerbera_harness import bootstrap
from gerbera_harness.configuration import HarnessSettings
from gerbera_protocol import ReadinessReport


@pytest.fixture
def configured_app(monkeypatch):
    settings = HarnessSettings.model_validate({
        "model": {"name": "test"},
        "connector": {"mcp_url": "https://sdk.example/mcp"},
    })
    connector = SimpleNamespace(
        tools=SimpleNamespace(list_tools=AsyncMock(return_value=[])),
        resources=SimpleNamespace(read_resource=AsyncMock()),
        connect=AsyncMock(),
        health=AsyncMock(return_value=ReadinessReport(service="sdk", phase="ready")),
    )
    connectors = []

    def construct_connector(url):
        connectors.append(connector)
        return connector

    monkeypatch.setattr(bootstrap, "load_settings", lambda: (settings, Path(".")))
    monkeypatch.setattr(bootstrap, "default_model_registry",
                        lambda: SimpleNamespace(build=lambda config: SimpleNamespace(complete=AsyncMock())))
    monkeypatch.setattr(bootstrap, "GerberaSdkConnector", construct_connector)
    return SimpleNamespace(app=bootstrap.create_server_app(), connector=connector, instances=connectors)


def test_bootstrap_reuses_one_connector_for_startup_and_runtime(configured_app) -> None:
    async def scenario():
        async with configured_app.app.router.lifespan_context(configured_app.app):
            pass

    asyncio.run(scenario())

    assert (len(configured_app.instances), configured_app.connector.connect.await_count,
            configured_app.connector.tools.list_tools.await_count) == (1, 1, 1)


def test_configured_harness_becomes_unready_when_remote_sdk_degrades(configured_app) -> None:
    async def scenario():
        async with configured_app.app.router.lifespan_context(configured_app.app):
            configured_app.connector.health.return_value = ReadinessReport(
                service="sdk", phase="degraded",
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(configured_app.app), base_url="http://harness",
            ) as client:
                return (await client.get("/ready")).status_code

    assert asyncio.run(scenario()) == 503


def test_configured_harness_refuses_startup_when_sdk_is_unready(configured_app) -> None:
    configured_app.connector.health.return_value = ReadinessReport(
        service="sdk", phase="starting",
    )

    async def scenario():
        async with configured_app.app.router.lifespan_context(configured_app.app):
            raise AssertionError("Startup should not complete")

    with pytest.raises(RuntimeError, match="SDK is not ready"):
        asyncio.run(scenario())

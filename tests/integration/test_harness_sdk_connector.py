import asyncio
from types import SimpleNamespace

from fastmcp import Client, FastMCP

from gerbera_harness.connectors import gerbera as connector_module
from gerbera_harness.connectors.gerbera import GerberaSdkConnector
from gerbera_protocol import ReadinessReport, RuntimeManifest
from gerbera_sdk.models.runtime.server.server_runtime import ServerRuntime


def test_connector_reads_sdk_resources_without_sharing_python_objects(monkeypatch):
    app = FastMCP("test-sdk")
    runtime = SimpleNamespace(
        app=app,
        hardware_system=SimpleNamespace(id="robot-1", name="robot", description="test", cameras=[]),
        hardware_plan=SimpleNamespace(boards=[]),
        hardware_runtime=SimpleNamespace(get_state_store=lambda: {"led": "off"}),
        model_runtime=SimpleNamespace(get_model_state=lambda: {}),
        event_listener=SimpleNamespace(get_health=lambda: {}),
    )
    ServerRuntime.register_remote_resources(runtime)

    monkeypatch.setattr(connector_module, "Client", lambda url: Client(app))
    connector = GerberaSdkConnector("https://remote-sdk.example/mcp")

    async def scenario():
        manifest = await connector.resources.read_resource("gerbera://manifest")
        snapshot = await connector.resources.read_resource("gerbera://hardware/state")
        return RuntimeManifest.model_validate(manifest), snapshot

    manifest, snapshot = asyncio.run(scenario())

    assert (manifest.model_dump(), snapshot) == (
        {"instance_id": "robot-1", "protocol_version": "1"}, {"led": "off"},
    )


def test_connector_reads_service_readiness_not_just_listener_health(monkeypatch):
    app = FastMCP("readiness-sdk")
    report = ReadinessReport(service="sdk", phase="degraded", reasons=("Camera unavailable",))

    @app.resource("gerbera://readiness", mime_type="application/json")
    def readiness() -> str:
        return report.model_dump_json()

    monkeypatch.setattr(connector_module, "Client", lambda url: Client(app))

    assert asyncio.run(GerberaSdkConnector("https://remote-sdk.example/mcp").health()) == report

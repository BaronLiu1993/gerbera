from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv
from starlette.applications import Starlette

from gerbera_harness.api.app import create_app
from gerbera_harness.configuration import HarnessSettings
from gerbera_harness.connectors.gerbera import GerberaSdkConnector
from gerbera_harness.extensions import (
    DatabaseToolsExtension, EventRecordingExtension, HardwareContextExtension,
    PhysicalStateProjection, SandboxExtension,
)
from gerbera_harness.extensions.recording import MemoryEventStore
from gerbera_harness.infrastructure.database import DatabaseGateway
from gerbera_harness.infrastructure.sandbox import SandboxGateway
from gerbera_harness.models.registry import default_model_registry
from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import Harness, HarnessBuilder
from gerbera_harness.runtime.state_machine.loader import unique_json_object
from gerbera_harness.runtime.workflows.presets import simple_workflow, structured_workflow
from gerbera_harness.tools.sources import CompositeToolSource, LocalToolSource


def load_settings() -> tuple[HarnessSettings, Path]:
    load_dotenv()
    path = Path(os.environ.get("GERBERA_HARNESS_CONFIG", ".gerbera/harness/harness.json"))
    if path.is_file():
        import json

        payload = json.loads(path.read_text(), object_pairs_hook=unique_json_object)
        return HarnessSettings.model_validate(payload), path.parent
    if "GERBERA_HARNESS_CONFIG" in os.environ:
        raise FileNotFoundError(f"Harness configuration not found: {path}")
    payload = {
        "model": {
            "type": os.environ.get("GERBERA_MODEL_TYPE", "api"),
            "provider": os.environ.get("PROVIDER", "openai"),
            "name": os.environ["GERBERA_MODEL"],
        },
    }
    if "MCP_URL" in os.environ:
        payload["connector"] = {"mcp_url": os.environ["MCP_URL"]}
    return HarnessSettings.model_validate(payload), path.parent


def build_harness(settings: HarnessSettings, root: Path) -> Harness:
    model = default_model_registry().build(settings.model)
    sources = [LocalToolSource()]
    connector = None
    if settings.connector is not None:
        connector = GerberaSdkConnector(settings.connector.mcp_url)
        sources.append(connector.tools)
    tools = CompositeToolSource(tuple(sources))
    services = HarnessServices(model, tools, connector.resources if connector else None)
    builder = HarnessBuilder(services)
    builder.with_extension(HardwareContextExtension(
        tools, connector.resources if connector else None,
    ))
    if connector is not None and settings.connector.physical_state:
        builder.with_extension(PhysicalStateProjection(connector.resources))
    install_extensions(builder, settings)
    if not settings.workflows:
        preset = {"simple": simple_workflow, "structured": structured_workflow}
        if settings.default_workflow not in preset:
            raise ValueError("Custom default workflows require an explicit workflow file")
        builder.with_workflow(preset[settings.default_workflow]())
    for name, path in settings.workflows.items():
        builder.with_workflow_file(Path(path), root)
        if name not in builder.workflows:
            raise ValueError(f"Workflow name does not match configured name: {name}")
    if settings.default_workflow not in builder.workflows:
        raise ValueError("The configured default workflow is not registered")
    return builder.build()


def install_extensions(builder: HarnessBuilder, settings: HarnessSettings) -> None:
    if len(set(settings.extensions)) != len(settings.extensions):
        raise ValueError("Duplicate harness extensions")
    if "event_recording" in settings.extensions:
        builder.with_extension(EventRecordingExtension(MemoryEventStore()))
    if "sandbox" in settings.extensions:
        builder.with_extension(SandboxExtension(SandboxGateway()))
    if "database" in settings.extensions:
        database = DatabaseGateway(
            host=os.environ["GERBERA_DATABASE_HOST"],
            port=os.environ["GERBERA_DATABASE_PORT"],
            db_name=os.environ["GERBERA_DATABASE_NAME"],
            read_user=os.environ["GERBERA_READER_USER"],
            read_password=os.environ["GERBERA_READER_PASSWORD"],
        )
        builder.with_extension(DatabaseToolsExtension(database))


def create_server_app() -> Starlette:
    settings, root = load_settings()
    harness = build_harness(settings, root)
    application = create_app(harness)
    application_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: Starlette):
        if settings.connector is not None:
            await GerberaSdkConnector(settings.connector.mcp_url).connect()
        await harness.services.tools.list_tools()
        async with application_lifespan(app):
            yield

    application.router.lifespan_context = lifespan
    return application

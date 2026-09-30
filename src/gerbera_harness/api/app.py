import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.api.orchestrator import Orchestrator
from gerbera_harness.infrastructure.database import DatabaseGateway
from gerbera_harness.infrastructure.sandbox import SandboxGateway
from gerbera_harness.tools.database import (
    GetTableSchemasTool,
    QueryDatabaseTool,
)
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sandbox import RunSandboxTool

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HarnessApiSettings:
    provider: str
    api_key: str
    mcp_url: str
    database_host: str
    database_port: str
    database_name: str
    database_reader_user: str
    database_reader_password: str

    @classmethod
    def from_environment(cls) -> "HarnessApiSettings":
        load_dotenv()
        return cls(
            provider=os.environ["PROVIDER"],
            api_key=os.environ["API_KEY"],
            mcp_url=os.environ["MCP_URL"],
            database_host=os.environ["GERBERA_DATABASE_HOST"],
            database_port=os.environ["GERBERA_DATABASE_PORT"],
            database_name=os.environ["GERBERA_DATABASE_NAME"],
            database_reader_user=os.environ["GERBERA_READER_USER"],
            database_reader_password=os.environ["GERBERA_READER_PASSWORD"],
        )


@dataclass(frozen=True)
class HarnessApiDependencies:
    settings: HarnessApiSettings
    orchestrator: Orchestrator


def build_dependencies(settings: HarnessApiSettings) -> HarnessApiDependencies:
    database = DatabaseGateway(
        host=settings.database_host,
        port=settings.database_port,
        db_name=settings.database_name,
        read_user=settings.database_reader_user,
        read_password=settings.database_reader_password,
    )
    local_tool_registry = LocalToolRegistry()
    local_tool_registry.register(GetTableSchemasTool(database=database))
    local_tool_registry.register(QueryDatabaseTool(database=database))
    local_tool_registry.register(RunSandboxTool(sandbox=SandboxGateway()))
    return HarnessApiDependencies(
        settings=settings,
        orchestrator=Orchestrator(local_tool_registry=local_tool_registry),
    )


@dataclass
class HarnessApi:
    dependencies: HarnessApiDependencies | None = None

    def require_dependencies(self) -> HarnessApiDependencies:
        if self.dependencies is None:
            self.dependencies = build_dependencies(
                HarnessApiSettings.from_environment()
            )
        return self.dependencies

    async def inference(self, request: Request) -> JSONResponse:
        dependencies = self.require_dependencies()
        try:
            body = await request.json()
            model = body["model"]
            user_prompt = body["user_prompt"]
        except (KeyError, TypeError, ValueError) as error:
            return JSONResponse({"error": str(error)}, status_code=400)

        try:
            agent_runtime = dependencies.orchestrator.initialise_agent_runtimes(
                user_prompt=user_prompt,
                mcp_url=dependencies.settings.mcp_url,
                provider=dependencies.settings.provider,
                api_key=dependencies.settings.api_key,
                model=model,
            )
            result = await agent_runtime.run_agent()
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        except Exception:
            LOGGER.exception("Unhandled inference request failure")
            return JSONResponse(
                {"error": "Internal server error"},
                status_code=500,
            )

        return JSONResponse(
            {
                "session_id": agent_runtime.session.session_id,
                "result": result.model_dump(mode="json"),
            },
            status_code=200,
        )

    async def health_check(self, _request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"}, status_code=200)


def create_app(dependencies: HarnessApiDependencies | None = None) -> Starlette:
    api = HarnessApi(dependencies=dependencies)
    routes = [
        Route("/health", endpoint=api.health_check, methods=["GET"]),
        Route("/inference", endpoint=api.inference, methods=["POST"]),
    ]
    return Starlette(debug=False, routes=routes)


app = create_app()

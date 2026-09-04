import os
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.infrastructure.database import DatabaseGateway
from gerbera_harness.api.orchestrator import Orchestrator
from gerbera_harness.infrastructure.sandbox import SandboxGateway
from gerbera_harness.tools.database import (
    GetTableSchemasTool,
    QueryDatabaseTool,
)
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sandbox import RunSandboxTool
load_dotenv()


host = os.environ["GERBERA_DATABASE_HOST"]
port = os.environ["GERBERA_DATABASE_PORT"]
db_name = os.environ["GERBERA_DATABASE_NAME"]
user = os.environ["GERBERA_READER_USER"]
password = os.environ["GERBERA_READER_PASSWORD"]

# From runtime
provider = os.environ["PROVIDER"]
api_key = os.environ["API_KEY"]
mcp_url = os.environ["MCP_URL"]

database = DatabaseGateway(
    host=host,
    port=port,
    db_name=db_name,
    read_user=user,
    read_password=password,
)

sandbox = SandboxGateway()

local_tool_registry = LocalToolRegistry()
local_tool_registry.register(GetTableSchemasTool(database=database))
local_tool_registry.register(QueryDatabaseTool(database=database))
local_tool_registry.register(RunSandboxTool(sandbox=sandbox))
orchestrator = Orchestrator(local_tool_registry=local_tool_registry)

async def inference(request):
    try:
        body = await request.json()

        model = body["model"]
        user_prompt = body["user_prompt"]

        # In the future 
        agent_runtime = orchestrator.initialise_agent_runtimes(
            user_prompt=user_prompt,
            mcp_url=mcp_url,
            provider=provider,
            api_key=api_key,
            model=model,
        )

        result = await agent_runtime.run_agent()
        return JSONResponse(
            {
                "session_id": agent_runtime.session.session_id,
                "result": result.model_dump(mode="json"),
            },
            status_code=200,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def health_check(request):
    return JSONResponse({"status": "healthy"}, status_code=200)


routes = [
    Route("/health", endpoint=health_check, methods=["GET"]),
    Route("/inference", endpoint=inference, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes)

import os
import json
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.gateway.database_gateway import DatabaseGateway
from gerbera_harness.server.orchestrator import Orchestrator

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
    host=host, port=port, db_name=db_name, user=user, password=password
)
orchestrator = Orchestrator()

async def inference(request):
    try:
        body = await request.json()

        model = body["model"]
        user_prompt = body["user_prompt"]

        agent_runtime = orchestrator.initialise_agent_runtimes(
            user_prompt=user_prompt,
            mcp_url=mcp_url,
            provider=provider,
            api_key=api_key,
            model=model,
            database=database
        )

        await agent_runtime.run_agent(initial_user_prompt=user_prompt)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def health_check(request):
    return JSONResponse({"status": "healthy"}, status_code=200)


routes = [
    Route("/health", endpoint=health_check, methods=["GET"]),
    Route("/inference", endpoint=inference, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes)

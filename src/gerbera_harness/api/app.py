from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.api.runs import RunApi
from gerbera_harness.runtime.harness import BaseHarness
from gerbera_harness.runtime.runs import RunManager


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy"})


def create_app(harness: BaseHarness | None = None) -> Starlette:
    manager = RunManager(harness) if harness is not None else None

    @asynccontextmanager
    async def lifespan(application: Starlette):
        try:
            yield
        finally:
            if manager is not None:
                await manager.close()

    routes = [Route("/health", health_check, methods=["GET"])]
    if manager is not None:
        api = RunApi(manager)
        routes.extend(api.routes())
        routes.append(Route("/inference", api.inference, methods=["POST"]))
    else:
        async def unconfigured(request: Request) -> JSONResponse:
            return JSONResponse({"error": "Harness is not configured"}, status_code=503)

        routes.append(Route("/inference", unconfigured, methods=["POST"]))
    application = Starlette(debug=False, routes=routes, lifespan=lifespan)
    application.state.run_manager = manager
    return application


app = create_app()

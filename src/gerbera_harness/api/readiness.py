from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.runtime.readiness import HarnessReadiness


def install_readiness(application: Starlette, readiness: HarnessReadiness) -> None:
    async def ready(request: Request) -> JSONResponse:
        report = await readiness.snapshot()
        return JSONResponse(report.model_dump(mode="json"), status_code=200 if report.ready else 503)

    application.router.routes.append(Route("/ready", ready, methods=["GET"]))

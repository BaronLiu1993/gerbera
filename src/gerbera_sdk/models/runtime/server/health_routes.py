import asyncio
from dataclasses import dataclass

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from gerbera_sdk.models.runtime.server.readiness import RuntimeReadiness


@dataclass
class HealthRoutes:
    app: FastMCP
    readiness: RuntimeReadiness

    def register(self) -> None:
        self.app.custom_route("/health", methods=["GET"])(self.health)
        self.app.custom_route("/ready", methods=["GET"])(self.ready)
        self.app.resource("gerbera://readiness", mime_type="application/json")(self.runtime_readiness)

    async def health(self, request: Request) -> JSONResponse:
        return JSONResponse({"service": "sdk", "status": "alive"})

    async def ready(self, request: Request) -> JSONResponse:
        report = await asyncio.to_thread(self.readiness.snapshot)
        return JSONResponse(report.model_dump(mode="json"), status_code=200 if report.ready else 503)

    def runtime_readiness(self) -> str:
        return self.readiness.snapshot().model_dump_json()

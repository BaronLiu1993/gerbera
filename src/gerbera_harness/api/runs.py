import asyncio
import json

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gerbera_harness.runtime.runs import RunCapacityError, RunManager
from gerbera_harness.runtime.state_machine.schemas import RunRequest


class RunApi:
    def __init__(self, manager: RunManager) -> None:
        self.manager = manager

    def routes(self) -> list[Route]:
        return [
            Route("/runs", self.start, methods=["POST"]),
            Route("/runs/{run_id}", self.get, methods=["GET"]),
            Route("/runs/{run_id}/cancel", self.cancel, methods=["POST"]),
            Route("/runs/{run_id}/events", self.events, methods=["GET"]),
        ]

    async def start(self, request: Request) -> JSONResponse:
        try:
            payload = bytearray()
            async for chunk in request.stream():
                payload.extend(chunk)
                if len(payload) > self.manager.limits.maximum_request_bytes:
                    return JSONResponse({"error": "Request is too large"}, status_code=413)
            run_request = RunRequest.model_validate(json.loads(payload))
            record = self.manager.start(run_request)
        except (ValidationError, ValueError):
            return JSONResponse({"error": "Invalid run request or workflow input"}, status_code=422)
        except RunCapacityError as error:
            return JSONResponse({"error": str(error)}, status_code=503)
        return JSONResponse(record.snapshot(), status_code=202)

    async def inference(self, request: Request) -> JSONResponse:
        response = await self.start(request)
        if response.status_code != 202:
            return response
        payload = json.loads(response.body)
        record = self.manager.get(payload["run_id"])
        await asyncio.shield(record.task)
        return JSONResponse(record.snapshot())

    async def get(self, request: Request) -> JSONResponse:
        try:
            return JSONResponse(self.manager.get(request.path_params["run_id"]).snapshot())
        except KeyError:
            return JSONResponse({"error": "Run not found"}, status_code=404)

    async def cancel(self, request: Request) -> JSONResponse:
        try:
            record = self.manager.cancel(request.path_params["run_id"])
            return JSONResponse(record.snapshot(), status_code=202)
        except KeyError:
            return JSONResponse({"error": "Run not found"}, status_code=404)

    async def events(self, request: Request) -> JSONResponse:
        try:
            record = self.manager.get(request.path_params["run_id"])
            after = int(request.query_params.get("after", "0"))
            limit = int(request.query_params.get("limit", "100"))
            if after < 0 or not 1 <= limit <= 1000:
                raise ValueError("Invalid pagination")
        except KeyError:
            return JSONResponse({"error": "Run not found"}, status_code=404)
        except ValueError:
            return JSONResponse({"error": "Invalid event cursor or limit"}, status_code=422)
        events = [event for event in record.events if event.id > after][:limit]
        oldest_id = record.events[0].id if record.events else None
        return JSONResponse({
            "events": [event.model_dump(mode="json") for event in events],
            "next_cursor": events[-1].id if events else after,
            "oldest_cursor": oldest_id,
            "truncated": oldest_id is not None and after < oldest_id - 1,
        })

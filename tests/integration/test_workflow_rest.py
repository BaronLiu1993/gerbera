import asyncio

import httpx

from gerbera_harness.api.app import create_app
from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import Harness
from gerbera_harness.tools.sources import LocalToolSource


class AnswerModel:
    async def complete(self, request):
        return {"outcome": "complete", "message": "hello", "calls": []}


def test_rest_run_can_be_started_polled_and_inspected():
    async def scenario():
        harness = Harness.simple(HarnessServices(AnswerModel(), LocalToolSource()))
        app = create_app(harness)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            started = await client.post("/runs", json={"workflow": "simple", "input": {"prompt": "hello"}})
            run_id = started.json()["run_id"]
            await app.state.run_manager.get(run_id).task
            result = await client.get(f"/runs/{run_id}")
            events = await client.get(f"/runs/{run_id}/events?after=0&limit=100")
            return started.status_code, result.json(), events.json()

    status, result, events = asyncio.run(scenario())

    assert (status, result["status"], result["output"], events["events"][-1]["type"]) == (
        202, "succeeded", {"message": "hello"}, "run.succeeded",
    )


def test_rest_rejects_unknown_workflow_and_invalid_input():
    async def scenario():
        harness = Harness.simple(HarnessServices(AnswerModel(), LocalToolSource()))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(harness)), base_url="http://test") as client:
            responses = await asyncio.gather(
                client.post("/runs", json={"workflow": "../../private", "input": {}}),
                client.post("/runs", json={"workflow": "simple", "input": {"prompt": ""}}),
                client.get("/runs/missing"),
            )
            return [response.status_code for response in responses]

    assert asyncio.run(scenario()) == [422, 422, 404]

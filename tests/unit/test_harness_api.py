import asyncio

import httpx

from gerbera_harness.api.app import create_app


def test_health_check_does_not_require_runtime_environment() -> None:
    async def request_health_check() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(request_health_check())

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_application_only_registers_implemented_routes() -> None:
    route_paths = {
        route.path
        for route in create_app().routes
        if hasattr(route, "path")
    }

    assert route_paths == {"/health", "/inference"}

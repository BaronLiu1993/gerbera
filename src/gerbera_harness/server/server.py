from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def health_check(request):
    return JSONResponse({"status": "healthy"}, status_code=200)


routes = [
    Route("/health", endpoint=health_check, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)

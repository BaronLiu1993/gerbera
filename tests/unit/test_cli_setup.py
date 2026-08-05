import importlib

import httpx


setup = importlib.import_module("gerbera_cli.setup.setup")


def test_ngrok_targets_the_ipv4_runtime(monkeypatch) -> None:
    captured = {}
    process = object()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        return process

    monkeypatch.setattr(setup.subprocess, "Popen", fake_popen)

    assert setup._start_ngrok("8000") is process
    assert captured["command"] == [
        "ngrok",
        "http",
        "http://127.0.0.1:8000",
    ]


def test_poll_public_endpoint_uses_httpx(monkeypatch) -> None:
    request = httpx.Request(
        "GET",
        "http://127.0.0.1:4040/api/tunnels",
    )
    responses = [
        httpx.ConnectError("ngrok is starting", request=request),
        httpx.Response(
            200,
            request=request,
            json={
                "tunnels": [
                    {"public_url": "https://example.ngrok.app"}
                ]
            },
        ),
    ]
    requested = []

    def fake_get(url: str, timeout: float):
        requested.append((url, timeout))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(setup.httpx, "get", fake_get)
    monkeypatch.setattr(setup.time, "sleep", lambda _seconds: None)

    public_endpoint = setup._poll_public_endpoint()

    assert public_endpoint == "https://example.ngrok.app"
    assert requested == [
        ("http://127.0.0.1:4040/api/tunnels", 1),
        ("http://127.0.0.1:4040/api/tunnels", 1),
    ]

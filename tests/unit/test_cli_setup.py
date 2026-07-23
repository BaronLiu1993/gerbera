import importlib


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

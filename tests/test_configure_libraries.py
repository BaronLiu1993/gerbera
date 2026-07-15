import subprocess
from types import SimpleNamespace

from typer.testing import CliRunner

from gerbera_cli.initialise import install_library
from gerbera_cli.main import app


runner = CliRunner()


def test_install_library_runs_arduino_cli(monkeypatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(install_library.subprocess, "run", fake_run)

    installed_library = install_library._install_library("Adafruit NeoPixel")

    assert installed_library == "Adafruit NeoPixel"
    assert calls == [
        (
            ["arduino-cli", "lib", "install", "Adafruit NeoPixel"],
            {"check": True, "text": True, "capture_output": True},
        )
    ]


def test_install_command_installs_library(monkeypatch) -> None:
    calls = []

    def fake_install(library_name: str) -> str:
        calls.append(library_name)
        return library_name

    monkeypatch.setattr(install_library, "_install_library", fake_install)

    result = runner.invoke(app, ["configure_libraries", "install", "Adafruit NeoPixel"])

    assert result.exit_code == 0
    assert calls == ["Adafruit NeoPixel"]
    assert "[gerbera-cli] installed library Adafruit NeoPixel" in result.stdout


def test_install_command_handles_cli_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        install_library,
        "_install_library",
        lambda library_name: (_ for _ in ()).throw(
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["arduino-cli", "lib", "install", "Adafruit NeoPixel"],
                stderr="download failed",
            )
        ),
    )

    result = runner.invoke(app, ["configure_libraries", "install", "Adafruit NeoPixel"])

    assert result.exit_code == 1
    assert "[gerbera-cli] failed to install library Adafruit NeoPixel" in result.stdout
    assert "download failed" in result.stdout

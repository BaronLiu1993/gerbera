import json
from pathlib import Path
import subprocess

from typer.testing import CliRunner

from gerbera_cli.configuration import ProjectConfig
from gerbera_cli.main import app
from gerbera_sdk.server.initialise import initialise_sdk


def test_init_delegates_hardware_scaffolding_to_sdk(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gerbera_sdk.server.initialise.discover_boards", lambda: {
        "/dev/board-1": {
            "id": "board-1", "address": "/dev/board-1",
            "protocol": "serial", "fqbn": "arduino:avr:uno",
        },
    })
    commands = []

    def run_service(command, **kwargs):
        commands.append(command[2:])
        initialise_sdk(Path(".gerbera/sdk/runtime.json"))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("gerbera_cli.initialise.subprocess.run", run_service)
    result = CliRunner().invoke(app, ["init"])
    if result.exception:
        raise result.exception
    compile(Path("index.py").read_text(), "index.py", "exec")

    assert (
        commands, set(ProjectConfig.load().services),
        set(json.loads(Path(".gerbera/secrets/sdk.json").read_text())),
        json.loads(Path(".gerbera/sdk/runtime.json").read_text())["devices"]["/dev/board-1"]["id"],
    ) == (
        [["gerbera_sdk.server", "initialise"]], {"sdk", "harness", "database"},
        {"gerbera_schema_password", "gerbera_writer_password"}, "board-1",
    )


def test_init_can_resume_after_harness_setup_was_cancelled(monkeypatch, tmp_path: Path) -> None:
    from gerbera_cli.initialise import initialise_project_files

    monkeypatch.chdir(tmp_path)
    attempts = []

    def run_service(command, **kwargs):
        attempts.append(command[2])
        if command[2] == "gerbera_harness.initialise" and attempts.count(command[2]) == 1:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("gerbera_cli.initialise.subprocess.run", run_service)
    import pytest

    with pytest.raises(subprocess.CalledProcessError):
        initialise_project_files(True, None)
    original = Path(".gerbera/secrets/database.env").read_text()

    initialise_project_files(True, None)

    assert Path(".gerbera/secrets/database.env").read_text() == original

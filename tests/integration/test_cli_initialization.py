import json
from pathlib import Path
import subprocess

from typer.testing import CliRunner

from gerbera_cli.configuration import ProjectConfig, ProjectSecrets
from gerbera_cli.main import app


def test_init_creates_runnable_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    board_output = json.dumps(
        {
            "detected_ports": [
                {
                    "port": {
                        "address": "/dev/board-1",
                        "protocol": "serial",
                    },
                    "matching_boards": [
                        {
                            "name": "Arduino Uno",
                            "fqbn": "arduino:avr:uno",
                        }
                    ],
                }
            ]
        }
    )

    def detect_board(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, board_output, "")

    monkeypatch.setattr(subprocess, "run", detect_board)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init"])
    config = ProjectConfig.load(Path("gerbera.yaml"))
    secrets = ProjectSecrets.load()
    compile(Path("index.py").read_text(), "index.py", "exec")
    created_paths = (
        Path("gerbera.yaml").is_file(),
        Path(".gerbera/secrets/secrets.json").is_file(),
        Path("index.py").is_file(),
    )

    assert (
        result.exit_code,
        len(config.devices),
        bool(secrets.gerbera_admin_password),
        created_paths,
    ) == (0, 1, True, (True, True, True))

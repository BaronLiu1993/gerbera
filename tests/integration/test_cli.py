import pytest
from typer.testing import CliRunner

from gerbera_cli.main import app


@pytest.mark.parametrize("command", ["init", "up", "server", "down", "status", "logs", "doctor"])
def test_cli_exposes_deployment_workflows(command) -> None:
    assert command in CliRunner().invoke(app, ["--help"]).stdout


def test_cli_has_no_manual_firmware_command() -> None:
    assert "firmware" not in CliRunner().invoke(app, ["--help"]).stdout


@pytest.mark.parametrize("option", ["--skip-flash", "--force"])
def test_up_cannot_bypass_sdk_preparation(option) -> None:
    assert CliRunner().invoke(app, ["up", option]).exit_code == 2

import pytest
from typer.testing import CliRunner

from gerbera_cli.main import app


def test_cli_exposes_deployment_workflows() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert all(command in result.stdout for command in ("init", "up", "server", "down", "status", "logs", "doctor"))
    assert "firmware" not in result.stdout


@pytest.mark.parametrize("option", ["--skip-flash", "--force"])
def test_up_cannot_bypass_sdk_preparation(option) -> None:
    assert CliRunner().invoke(app, ["up", option]).exit_code == 2

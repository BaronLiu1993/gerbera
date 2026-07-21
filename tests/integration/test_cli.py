from typer.testing import CliRunner

from gerbera_cli.main import app


def test_cli_exposes_supported_workflows() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "setup" in result.stdout
    assert "deploy" in result.stdout

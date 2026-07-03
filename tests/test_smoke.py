from typer.testing import CliRunner

from cli_app.main import app


def test_help_renders() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "CLI scaffold." in result.stdout

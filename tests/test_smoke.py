from typer.testing import CliRunner

from gerbera_cli.main import app


def test_help_renders() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Gerbera CLI." in result.stdout
    assert "configure_libraries" in result.stdout
    assert "devices" in result.stdout

import typer

from cli_app.commands.detect_devices import app as detect_devices_app
from cli_app.commands.root import app as root_app

app = typer.Typer(
    help="CLI scaffold.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(root_app, name="hello")
app.add_typer(detect_devices_app, name="devices")


def run() -> None:
    app()

import typer

from gerbera_cli.commands.configure_libraries import app as configure_libraries_app
from gerbera_cli.commands.detect_devices import app as detect_devices_app
from gerbera_cli.commands.set_connections import app as connections_app

app = typer.Typer(
    help="Gerbera CLI.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(detect_devices_app, name="devices")
app.add_typer(connections_app, name="connections")
app.add_typer(configure_libraries_app, name="configure_libraries")


def run() -> None:
    app()


if __name__ == "__main__":
    run()

import typer

from gerbera_cli.commands.declare_devices_command import (
    declare_devices_command,
)
from gerbera_cli.commands.install_library_command import (
    install_library_command,
)

app = typer.Typer(
    help="Gerbera CLI.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(declare_devices_command, name="devices")
app.add_typer(install_library_command, name="configure_libraries")


def run() -> None:
    app()


if __name__ == "__main__":
    run()

import typer

from gerbera_cli.commands.detect_devices import app as detect_devices_app

app = typer.Typer(
    help="Gerbera CLI.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(detect_devices_app, name="devices")


def run() -> None:
    app()


if __name__ == "__main__":
    run()

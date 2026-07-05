import subprocess

import typer

from gerbera_cli.config import get_settings

app = typer.Typer(help="Configure Microcontroller libraries.")


def _install_library(library_name: str) -> str:
    subprocess.run(
        ["arduino-cli", "lib", "install", library_name],
        check=True,
        text=True,
        capture_output=True,
    )
    return library_name


@app.command("install")
def install_library(
    library_name: str = typer.Argument(..., help="Arduino library name to install."),
) -> None:
    settings = get_settings()

    try:
        installed_library = _install_library(library_name)
    except subprocess.CalledProcessError as exc:
        typer.echo(f"[{settings.app_name}] failed to install library {library_name}")
        if exc.stderr:
            typer.echo(exc.stderr.strip())
        raise typer.Exit(code=1) from exc

    typer.echo(f"[{settings.app_name}] installed library {installed_library}")

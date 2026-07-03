import typer

from gerbera_cli.config import get_settings

app = typer.Typer(help="Example command group.")


@app.command()
def world(name: str = "world") -> None:
    """Print a basic greeting."""
    settings = get_settings()
    typer.echo(f"[{settings.app_name}] hello, {name}")

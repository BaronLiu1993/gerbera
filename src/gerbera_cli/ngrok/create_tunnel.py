import subprocess

import typer

from gerbera_cli.config import get_settings

create_tunnel_command = typer.Typer(help="ngrok tunnel commands.")


@create_tunnel_command.command("http")
def create_http_tunnel(
    port: int = typer.Argument(..., help="Local HTTP port to expose."),
    domain: str = typer.Option("", "--domain", help="Reserved ngrok domain to use."),
) -> None:
    settings = get_settings()
    command = ["ngrok", "http", str(port)]

    if domain.strip():
        command.extend(["--domain", domain.strip()])

    typer.echo(
        f"[{settings.app_name}] starting ngrok tunnel for http://127.0.0.1:{port}"
    )

    try:
        subprocess.run(
            command,
            check=True,
        )
    except FileNotFoundError as exc:
        typer.echo(f"[{settings.app_name}] ngrok CLI not found on PATH")
        raise typer.Exit(code=1) from exc
    except subprocess.CalledProcessError as exc:
        typer.echo(f"[{settings.app_name}] failed to start ngrok tunnel")
        raise typer.Exit(code=1) from exc

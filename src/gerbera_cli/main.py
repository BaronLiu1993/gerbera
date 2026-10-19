import json

import typer

from gerbera_cli.configuration import ProjectConfig
from gerbera_cli.deployment import ProjectRuntime, StartupOptions
from gerbera_cli.setup import LocalProjectServices
from gerbera_cli.initialise import initialise_project_files

app = typer.Typer(no_args_is_help=True)


@app.command(name="init")
def initialise_project(
    with_harness: bool = typer.Option(False, "--with-harness"),
    provider: str | None = typer.Option(None, "--provider"),
) -> None:
    """Delegate service scaffolding and create a deployment manifest."""
    initialise_project_files(with_harness, provider)
    typer.echo("Project created. Run: gerbera up")


@app.command(name="up")
def up(no_harness: bool = typer.Option(False, "--no-harness")) -> None:
    runtime = build_project_runtime()
    runtime.start(StartupOptions(start_harness=not no_harness))
    print_status(runtime.status())


@app.command(name="server")
def server() -> None:
    """Launch the SDK in the foreground; the SDK owns all preparation."""
    LocalProjectServices(ProjectConfig.load()).run_server_foreground()


@app.command(name="status")
def status() -> None:
    print_status(build_project_runtime().status())


@app.command(name="logs")
def logs(follow: bool = typer.Option(False, "--follow", "-f")) -> None:
    build_project_runtime().logs(follow)


@app.command(name="doctor")
def doctor() -> None:
    """Display readiness reports from the services, without validating them locally."""
    print_status(build_project_runtime().doctor())


@app.command(name="down")
def down() -> None:
    build_project_runtime().stop()
    typer.echo("Managed services stopped.")


def build_project_runtime() -> ProjectRuntime:
    return ProjectRuntime(LocalProjectServices(ProjectConfig.load()))


def print_status(service_status: dict[str, object]) -> None:
    typer.echo(json.dumps(service_status, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

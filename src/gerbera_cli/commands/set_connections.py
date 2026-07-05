import typer
import json
from pathlib import Path

from gerbera_cli.commands.factories.connections_config import ConnectionsConfig, RoleEnum

app = typer.Typer(help="Configure logical functionality for board pins.")

CONNECTIONS_CONFIG_PATH = Path("connections.json")

def _load_connections_config(path: Path, library: str) -> ConnectionsConfig:
    if not path.exists():
        return ConnectionsConfig(library)

    payload = json.loads(path.read_text())
    for entry in payload.get("libraries", []):
        if entry.get("library") == library:
            return ConnectionsConfig.from_dict(entry)

    return ConnectionsConfig(library)


def _save_connections_config(path: Path, config: ConnectionsConfig) -> None:
    libraries = []
    if path.exists():
        payload = json.loads(path.read_text())
        libraries = payload.get("libraries", [])

    remaining = [entry for entry in libraries if entry.get("library") != config.library]
    remaining.append(config.to_dict())
    path.write_text(json.dumps({"libraries": remaining}, indent=2))


@app.command("set")
def set_connection(
    library: str,
    id: str,
    role: RoleEnum,
    pin: int,
    output: Path = CONNECTIONS_CONFIG_PATH,
) -> None:
    """Assign a logical role to a specific board pin."""
    config = _load_connections_config(output, library)
    added = config.add_functionality(id=id, role=role, pin=pin)

    if not added:
        typer.echo(f"Functionality '{id}' already exists in library '{library}'.")
        raise typer.Exit(code=1)

    _save_connections_config(output, config)
    typer.echo(f"Mapped '{id}' as '{role.value}' on pin {pin} in '{library}'.")

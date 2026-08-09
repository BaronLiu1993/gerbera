import json
from pathlib import Path
import subprocess
import questionary
import typer

from gerbera_cli.harness import run_local_harness
from gerbera_cli.initialise import default_config, load_board_data, CONFIG_PATH

app = typer.Typer()


@app.command(name="init")
def init():
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
    else:
        config = default_config()
    device_json = config["devices"]

    typer.echo("Fetching supported microcontrollers from arduino-cli...")

    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)
    detected_ports = load_board_data(
        data["detected_ports"],
        device_json,
    )
    choices = [board["address"] for board in detected_ports]

    selected_choices = questionary.checkbox(
        "Select microcontrollers to configure (Space to select, Enter to confirm):",
        choices=choices,
    ).ask()

    if not selected_choices:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    entry_point = questionary.text(
        "Define the app entry point:",
        default=config["entry_point"],
    ).ask()

    if not entry_point:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    hardware_name = questionary.text(
        "Define the hardware variable name:",
        default=config["hardware_name"],
    ).ask()

    if not hardware_name:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    for choice in selected_choices:
        for port in detected_ports:
            if port["address"] == choice:
                device_json[choice] = port

    config["devices"] = device_json
    config["entry_point"] = entry_point.strip()
    config["hardware_name"] = hardware_name.strip()

    Path(".gerbera/firmware").mkdir(parents=True, exist_ok=True)
    Path(".gerbera/models").mkdir(parents=True, exist_ok=True)
    Path(".gerbera/reactions").mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=4))
    typer.secho(
        "Successfully updated config and .gerbera workspace. "
        f"Currently managing {len(device_json)} device(s) in config.json.",
        fg=typer.colors.GREEN,
        bold=True,
    )


# Perform a check for a config file first before doing this
@app.command(name="harness")
def harness():
    choices = ["local", "cloud"]

    selection = questionary.select("Select Harness Deployment", choices).ask()

    if selection == "local":
        run_local_harness()
        config = json.loads(CONFIG_PATH.read_text())
        config["harness"] = {
            "type": "local",
            "host": "127.0.0.1",
            "port": 8000,
            "base_url": "http://127.0.0.1:8000",
        }
        CONFIG_PATH.write_text(json.dumps(config, indent=4))
    else:
        pass


def main():
    app()


if __name__ == "__main__":
    main()

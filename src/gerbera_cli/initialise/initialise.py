import json
import os
import uuid
import subprocess
import typer
import questionary

init_app = typer.Typer()
CONFIG_PATH = "config.json"

def _load_existing_config(filepath: str = CONFIG_PATH) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"devices": {}, "entry_point": ""}

def _load_existing_devices(filepath: str = CONFIG_PATH) -> dict:
    config = _load_existing_config(filepath)
    devices = config.get("devices", {})
    return devices if isinstance(devices, dict) else {}

def _raw_board_data_adapter(devices, existing_devices):
    board_data = []
    for device in devices:
        port = device["port"]
        address = port["address"]
        existing_device = existing_devices.get(address, {})
        device_id = existing_device.get("id") or str(uuid.uuid4())

        payload = {
            "id": device_id,
            "address": address,
            "protocol": port["protocol"],
        }
        board_data.append(payload)
    return board_data

@init_app.command()
def init():
    config = _load_existing_config()
    device_json = _load_existing_devices()

    typer.echo("Fetching supported microcontrollers from arduino-cli...")

    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True
    )
    
    data = json.loads(result.stdout)    
    detected_ports = _raw_board_data_adapter(data.get("detected_ports", []), device_json)
    choices = [
        f"{board['address']}" 
        for board in detected_ports
    ]
    
    selected_choices = questionary.checkbox(
        "Select microcontrollers to configure (Space to select, Enter to confirm):",
        choices=choices
    ).ask()

    if not selected_choices:
        typer.echo("Aborted (or no devices selected).")
        raise typer.Exit()
    
    typer.echo("You selected:")
    for dev in selected_choices:
        typer.echo(f" • {dev}")

    confirm = questionary.confirm("Do you want to write these to config?").ask()
    
    if not confirm:
        typer.echo("Operation canceled.")
        raise typer.Exit()

    entry_point = questionary.text(
        "Define the app entry point:",
        default="index",
    ).ask()

    if not entry_point:
        typer.echo("Operation canceled.")
        raise typer.Exit()

    for choice in selected_choices:
        for port in detected_ports:
            if port["address"] == choice:
                device_json[choice] = port

    config["devices"] = device_json
    config["entry_point"] = entry_point.strip()

    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        typer.secho(
            f"✓ Successfully updated config! Currently managing {len(device_json)} device(s) in config.json.",
            fg=typer.colors.GREEN, 
            bold=True
        )
    except IOError as e:
        typer.secho(f"Failed to write file: {e}", fg=typer.colors.RED)

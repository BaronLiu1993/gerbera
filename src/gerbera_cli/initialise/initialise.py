import json
import uuid
import subprocess

import questionary
import typer

from gerbera_cli.utils import CONFIG_PATH, _load_config


def _default_config() -> dict:
    return {
        "devices": {},
        "entry_point": "",
        "hardware_name": "hardware",
        "server": {"port": "", "host": ""},
    }


def _load_existing_devices(config: dict) -> dict:

    devices = config.get("devices", {})
    if not isinstance(devices, dict):
        raise ValueError("config.json['devices'] must be an object")

    return devices


def _load_existing_config() -> dict:
    try:
        return _load_config(CONFIG_PATH)
    except FileNotFoundError:
        return _default_config()
    except ValueError:
        if CONFIG_PATH.exists() and not CONFIG_PATH.read_text().strip():
            return _default_config()
        raise


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


def init():
    config = _load_existing_config()
    device_json = _load_existing_devices(config)

    typer.echo("Fetching supported microcontrollers from arduino-cli...")

    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)
    detected_ports = _raw_board_data_adapter(
        data.get("detected_ports", []),
        device_json,
    )
    choices = [board["address"] for board in detected_ports]

    selected_choices = questionary.checkbox(
        "Select microcontrollers to configure (Space to select, Enter to confirm):",
        choices=choices,
    ).ask()

    if not selected_choices:
        raise typer.Exit()

    typer.echo("You selected:")
    for dev in selected_choices:
        typer.echo(f" • {dev}")

    confirm = questionary.confirm("Do you want to write these to config?").ask()

    if not confirm:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    entry_point = questionary.text(
        "Define the app entry point:",
        default=str(config.get("entry_point", "")).strip() or "index.py",
    ).ask()

    if not entry_point:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    hardware_name = questionary.text(
        "Define the hardware variable name:",
        default=str(config.get("hardware_name", "")).strip() or "hardware",
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
    config["server"] = {"local_endpoint": "", "port": "", "public_endpoint": ""}
    config["harness"] = {"id": "", "ip_address": "", "created_at": ""}

    try:
        CONFIG_PATH.write_text(json.dumps(config, indent=4))
        typer.secho(
            f"✓ Successfully updated config! Currently managing {len(device_json)} device(s) in config.json.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    except OSError as exc:
        typer.secho(f"Failed to write file: {exc}", fg=typer.colors.RED)

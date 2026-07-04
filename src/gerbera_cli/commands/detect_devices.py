import json
from pathlib import Path
import sys
import termios
import tty
from uuid import uuid4

import serial.tools.list_ports as list_ports
import typer

from gerbera_cli.config import get_settings

app = typer.Typer(help="Serial device detection commands.")

DEVICE_MAP_PATH = Path("devices.json")
DEFAULT_BAUD_RATE = 115200


def _is_candidate_device(port) -> bool:
    if not port.hwid or port.hwid.lower() == "n/a":
        return False
    if not port.device or not port.description:
        return False
    return True


def _available_devices() -> list[dict]:
    devices = []

    for port in list_ports.comports():
        if not _is_candidate_device(port):
            continue

        devices.append(
            {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
            }
        )

    for index, device in enumerate(devices):
        device["index"] = index

    return devices


def _print_devices(devices: list[dict]) -> None:
    for device in devices:
        typer.echo(
            f"{device['index']}: {device['device']} | "
            f"{device['description']} | {device['hwid']}"
        )


def _read_menu_key() -> str:
    fd = sys.stdin.fileno()
    original_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        first = sys.stdin.read(1)
        if first == "\x1b":
            second = sys.stdin.read(1)
            third = sys.stdin.read(1)
            if second == "[" and third == "A":
                return "up"
            if second == "[" and third == "B":
                return "down"
            return "escape"
        if first in {"\r", "\n"}:
            return "enter"
        if first == "\x03":
            raise KeyboardInterrupt
        return first
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_settings)


def _render_selection_menu(
    devices: list[dict], cursor: int, selected_devices: dict[str, dict]
) -> None:
    typer.echo("\033[2J\033[H", nl=False)
    typer.echo("Select devices with Enter. Move with Up/Down. Choose Continue when done.\n")

    for index, device in enumerate(devices):
        is_selected = any(
            selected["device"] == device["device"] and selected["hwid"] == device["hwid"]
            for selected in selected_devices.values()
        )
        prefix = ">" if index == cursor else " "
        marker = "[x]" if is_selected else "[ ]"
        typer.echo(
            f"{prefix} {marker} {device['device']} | "
            f"{device['description']} | {device['hwid']}"
        )

    continue_index = len(devices)
    prefix = ">" if continue_index == cursor else " "
    typer.echo(f"{prefix} [ ] Continue")

    if selected_devices:
        typer.echo("\nCurrent mapping:")
        for device_id, selected in selected_devices.items():
            typer.echo(f"- {device_id}: {selected['device']}")


def _select_devices_interactively(devices: list[dict]) -> dict[str, dict]:
    selected_devices: dict[str, dict] = {}
    cursor = 0

    while True:
        _render_selection_menu(devices, cursor, selected_devices)
        key = _read_menu_key()

        if key == "up":
            cursor = (cursor - 1) % (len(devices) + 1)
            continue

        if key == "down":
            cursor = (cursor + 1) % (len(devices) + 1)
            continue

        if key != "enter":
            continue

        chosen = devices[cursor]
        if any(
            selected["device"] == chosen["device"] and selected["hwid"] == chosen["hwid"]
            for selected in selected_devices.values()
        ):
            continue

        device_id = str(uuid4())
        selected_devices[device_id] = {
            "id": device_id,
            "device": chosen["device"],
            "description": chosen["description"],
            "hwid": chosen["hwid"],
            "baud_rate": DEFAULT_BAUD_RATE
        }


@app.command("list")
def list_connected_devices() -> None:
    settings = get_settings()
    devices = _available_devices()

    if not devices:
        typer.echo(f"[{settings.app_name}] no serial devices detected")
        return

    _print_devices(devices)


@app.command("select")
def select_devices(output: Path = DEVICE_MAP_PATH) -> None:
    settings = get_settings()
    devices = _available_devices()

    if not devices:
        typer.echo(f"[{settings.app_name}] no serial devices detected")
        return

    selected_devices = _select_devices_interactively(devices)

    if not selected_devices:
        typer.echo(f"[{settings.app_name}] no devices selected")
        return

    output.write_text(json.dumps(selected_devices, indent=2))
    typer.echo(f"Wrote {len(selected_devices)} device mapping(s) to {output}")

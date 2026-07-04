import json
from pathlib import Path
import subprocess
import sys
import termios
import tty
from uuid import uuid4

import typer

from gerbera_cli.config import get_settings

app = typer.Typer(help="Serial device detection commands.")

DEVICE_MAP_PATH = Path("devices.json")
DEFAULT_BAUD_RATE = 115200


def _is_candidate_device(port: dict) -> bool:
    properties = port.get("properties", {})
    if not properties.get("vid") or not properties.get("pid"):
        return False
    if not port.get("address") or not port.get("label"):
        return False
    return True


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


def _available_devices() -> list[dict]:
    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True,
        check=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    devices = []

    for entry in payload.get("detected_ports", []):
        port = entry.get("port", {})
        if not _is_candidate_device(port):
            continue

        properties = port.get("properties", {})
        hwid = f"USB VID:PID={properties['vid']}:{properties['pid']}"
        if properties.get("serialNumber"):
            hwid = f"{hwid} SERIAL={properties['serialNumber']}"

        devices.append(
            {
                "device": port["address"],
                "description": port.get("protocol_label", port["label"]),
                "hwid": hwid,
            }
        )

    for index, device in enumerate(devices):
        device["index"] = index

    return devices


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

        if cursor == len(devices):
            return selected_devices

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
            "baud_rate": DEFAULT_BAUD_RATE,
        }

@app.command("select")
def select_devices(output: Path = DEVICE_MAP_PATH) -> None:
    settings = get_settings()
    devices = _available_devices()

    if not devices:
        typer.echo(f"[{settings.app_name}] no Arduino-compatible serial devices detected")
        return

    selected_devices = _select_devices_interactively(devices)

    if not selected_devices:
        typer.echo(f"[{settings.app_name}] no devices selected")
        return

    output.write_text(json.dumps(selected_devices, indent=2))
    typer.echo(f"Wrote {len(selected_devices)} device mapping(s) to {output}")

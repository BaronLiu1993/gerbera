import json
import os
from pathlib import Path
import subprocess
import uuid

import questionary

from gerbera_sdk.firmware.boards import BOARD_REGISTRY
from gerbera_sdk.server.configuration import RegisteredDevice, SdkSettings
from gerbera_sdk.server.hardware_registry import RegisteredHardwareRegistry


def discover_boards() -> dict[str, dict]:
    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    detected = {}
    for device in json.loads(result.stdout)["detected_ports"]:
        port = device["port"]
        matches = device.get("matching_boards", [])
        detected[port["address"]] = {
            "id": str(uuid.uuid4()), "address": port["address"],
            "protocol": port["protocol"], "fqbn": matches[0]["fqbn"] if len(matches) == 1 else None,
        }
    return detected


def initialise_sdk(path: Path) -> None:
    if path.exists():
        SdkSettings.load(path)
        return
    detected = discover_boards()
    if not detected:
        raise RuntimeError("No boards detected; connect a board on the SDK host and retry")
    addresses = list(detected)
    if len(addresses) > 1:
        addresses = questionary.checkbox("Select boards:", choices=addresses).ask()
    if not addresses:
        raise RuntimeError("SDK initialization cancelled")
    supported = list(BOARD_REGISTRY.definitions)
    devices = {}
    for address in addresses:
        device = detected[address]
        if device["fqbn"] not in supported:
            device["fqbn"] = questionary.select(f"Board type for {address}:", choices=supported).ask()
        devices[address] = RegisteredDevice.model_validate(device)
    root = Path.cwd()
    settings = SdkSettings(
        project_root=Path(os.path.relpath(root, path.parent.resolve())),
        hardware_registry=RegisteredHardwareRegistry(devices=tuple(devices.values())),
    )
    entry_point = root / settings.entry_point
    if entry_point.exists():
        raise FileExistsError(f"Hardware entry point already exists: {entry_point}; configure it explicitly")
    controllers = "\n\n".join(controller_source(index, device) for index, device in enumerate(devices.values(), 1))
    controller_names = ", ".join(f"microcontroller_{index}" for index in range(1, len(devices) + 1))
    entry_point.write_text(
        "from gerbera_sdk.models.hardware.hardware_system import HardwareSystem\n"
        "from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RuntimeTransportConfig\n\n\n"
        f"{controllers}\n\n"
        "hardware_system = HardwareSystem(\n"
        '    name="gerbera-project",\n'
        f"    microcontrollers=[{controller_names}],\n"
        ")\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2))


def controller_source(index: int, device: RegisteredDevice) -> str:
    return (
        f"microcontroller_{index} = Microcontroller(\n"
        f"    device_id={device.id!r},\n"
        f"    name='controller_{index}',\n"
        f"    upload_port={device.address!r},\n"
        f"    runtime_transport=RuntimeTransportConfig.usb_serial({device.address!r}),\n"
        f"    fqbn={device.fqbn!r},\n"
        ")"
    )

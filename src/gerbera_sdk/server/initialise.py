import json
import os
from pathlib import Path
import subprocess
import uuid

import questionary

from gerbera_sdk.firmware.boards import BOARD_REGISTRY
from gerbera_sdk.paths import FIRMWARE_PATH
from gerbera_sdk.server.configuration import RegisteredDevice, SdkSettings


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
            "protocol": port["protocol"], "fqbn": matches[0].get("fqbn") if matches else None,
        }
    return detected


def initialise_sdk(path: Path) -> None:
    if path.exists():
        for device in SdkSettings.load(path).devices.values():
            authorization = FIRMWARE_PATH / device.id / "provisioning.json"
            if not authorization.exists() and questionary.confirm(
                f"Authorize an initial firmware upload to {device.address} ({device.fqbn})? "
                "Only do this after checking the physical board and upload port.",
                default=False,
            ).ask():
                authorize_provisioning(device)
        return
    detected = discover_boards()
    if not detected:
        raise RuntimeError("No boards detected; connect a board on the SDK host and retry")
    addresses = list(detected)
    if len(addresses) > 1:
        addresses = questionary.checkbox("Select boards:", choices=addresses).ask()
    if not addresses:
        raise RuntimeError("SDK initialization cancelled")
    supported = [definition.fqbn for definition in BOARD_REGISTRY.definitions]
    devices = {}
    for address in addresses:
        device = detected[address]
        if device["fqbn"] not in supported:
            device["fqbn"] = questionary.select(f"Board type for {address}:", choices=supported).ask()
        devices[address] = RegisteredDevice.model_validate(device)
    root = Path.cwd()
    settings = SdkSettings(project_root=Path(os.path.relpath(root, path.parent.resolve())), devices=devices)
    entry_point = root / settings.entry_point
    if entry_point.exists():
        raise FileExistsError(f"Hardware entry point already exists: {entry_point}; configure it explicitly")
    controllers = ",\n".join(controller_source(index, device) for index, device in enumerate(devices.values(), 1))
    entry_point.write_text(
        "from gerbera_sdk.models.hardware.hardware_system import HardwareSystem\n"
        "from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RuntimeWatchdogConfig\n\n"
        'hardware_system = HardwareSystem(name="gerbera-project", microcontrollers=[\n'
        f"{controllers}\n])\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2))
    for device in devices.values():
        authorize_provisioning(device)


def authorize_provisioning(device: RegisteredDevice) -> None:
    directory = FIRMWARE_PATH / device.id
    directory.mkdir(parents=True, exist_ok=True)
    authorization = directory / "provisioning.json"
    authorization.touch(mode=0o600, exist_ok=False)
    authorization.write_text(json.dumps({
        "microcontroller_id": device.id, "fqbn": device.fqbn, "upload_port": device.address,
    }))


def controller_source(index: int, device: RegisteredDevice) -> str:
    return (
        f"    Microcontroller(name='controller_{index}', port={device.address!r}, fqbn={device.fqbn!r},\n"
        f"        device_id={device.id!r}, watchdog=RuntimeWatchdogConfig(\n"
        "            heartbeat_interval_ms=500, heartbeat_timeout_ms=2500)),"
    ).removesuffix(",")

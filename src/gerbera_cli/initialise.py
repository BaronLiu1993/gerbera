import uuid
from pathlib import Path

CONFIG_PATH = Path("config.json")

def default_config() -> dict:
    return {
        "devices": {},
        "entry_point": "index.py",
        "hardware_name": "hardware",
    }

def load_board_data(devices, existing_devices):
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

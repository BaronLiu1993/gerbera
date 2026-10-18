import json
import uuid
from typing import Any, Protocol


class CommandResult(Protocol):
    stdout: str


def load_board_data(
    raw_arduino_result: CommandResult,
) -> dict[str, dict[str, Any]]:
    detected_ports = json.loads(raw_arduino_result.stdout)["detected_ports"]

    board_data: dict[str, dict[str, Any]] = {}
    for device in detected_ports:
        port = device["port"]
        address = port["address"]
        matching_boards = device.get("matching_boards", [])
        payload: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "address": address,
            "protocol": port["protocol"],
        }
        if matching_boards:
            payload["fqbn"] = matching_boards[0].get("fqbn")
            payload["name"] = matching_boards[0].get("name")
        board_data[address] = payload
    return board_data

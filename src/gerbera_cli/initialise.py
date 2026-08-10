import uuid
import json

def load_board_data(raw_arduino_result):
    data = json.loads(raw_arduino_result.stdout)["detected_ports"]

    board_data = {}
    for device in data:
        port = device["port"]
        address = port["address"]
        protocol = port["protocol"]

        payload = {
            "id": str(uuid.uuid4()),
            "address": address,
            "protocol": protocol,
        }
        board_data["port"] = payload
    return board_data

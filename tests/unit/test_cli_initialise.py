import json
from types import SimpleNamespace

from gerbera_cli.initialise import load_board_data


def test_load_board_data_indexes_detected_ports_by_address() -> None:
    arduino_result = SimpleNamespace(
        stdout=json.dumps(
            {
                "detected_ports": [
                    {
                        "port": {
                            "address": "/dev/board-1",
                            "protocol": "serial",
                        }
                    }
                ]
            }
        )
    )

    boards = load_board_data(arduino_result)

    assert boards["/dev/board-1"]["address"] == "/dev/board-1"
    assert boards["/dev/board-1"]["protocol"] == "serial"


def test_load_board_data_returns_empty_mapping_without_detected_ports() -> None:
    arduino_result = SimpleNamespace(
        stdout=json.dumps({"detected_ports": []}),
    )

    assert load_board_data(arduino_result) == {}

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
                        },
                        "matching_boards": [
                            {
                                "name": "Arduino Uno",
                                "fqbn": "arduino:avr:uno",
                            }
                        ],
                    }
                ]
            }
        )
    )

    boards = load_board_data(arduino_result)

    assert boards["/dev/board-1"] | {"id": "ignored"} == {
        "id": "ignored",
        "address": "/dev/board-1",
        "protocol": "serial",
        "fqbn": "arduino:avr:uno",
        "name": "Arduino Uno",
    }


def test_load_board_data_returns_empty_mapping_without_detected_ports() -> None:
    arduino_result = SimpleNamespace(
        stdout=json.dumps({"detected_ports": []}),
    )

    assert load_board_data(arduino_result) == {}

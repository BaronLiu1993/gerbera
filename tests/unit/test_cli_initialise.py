import json
from types import SimpleNamespace

import pytest

from gerbera_sdk.server.initialise import discover_boards


@pytest.mark.parametrize("ports, expected", [
    ([], {}),
    ([{
        "port": {"address": "/dev/board-1", "protocol": "serial"},
        "matching_boards": [{"name": "Arduino Uno", "fqbn": "arduino:avr:uno"}],
    }], {"/dev/board-1": {
        "id": "board-1", "address": "/dev/board-1",
        "protocol": "serial", "fqbn": "arduino:avr:uno",
    }}),
])
def test_sdk_owns_board_discovery(monkeypatch, ports, expected) -> None:
    monkeypatch.setattr("gerbera_sdk.server.initialise.uuid.uuid4", lambda: "board-1")
    monkeypatch.setattr("gerbera_sdk.server.initialise.subprocess.run", lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps({"detected_ports": ports})))

    assert discover_boards() == expected

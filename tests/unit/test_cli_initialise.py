import json
from types import SimpleNamespace

import pytest

from gerbera_cli.initialise import initialise


class _Answer:
    def __init__(self, value) -> None:
        self.value = value

    def ask(self):
        return self.value


def test_empty_config_is_treated_as_first_run(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("")
    monkeypatch.setattr(initialise, "CONFIG_PATH", config_path)

    config = initialise._load_existing_config()

    assert config["devices"] == {}
    assert config["entry_point"] == ""
    assert config["hardware_name"] == "hardware"


def test_nonempty_invalid_config_still_fails(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("not-json")
    monkeypatch.setattr(initialise, "CONFIG_PATH", config_path)

    with pytest.raises(ValueError, match="not valid JSON"):
        initialise._load_existing_config()


def test_init_creates_config_and_gerbera_directories(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(initialise, "CONFIG_PATH", config_path)
    monkeypatch.setattr(
        initialise.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
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
        ),
    )
    monkeypatch.setattr(
        initialise.questionary,
        "checkbox",
        lambda *args, **kwargs: _Answer(["/dev/board-1"]),
    )
    monkeypatch.setattr(
        initialise.questionary,
        "confirm",
        lambda *args, **kwargs: _Answer(True),
    )

    answers = iter(["index.py", "hardware"])
    monkeypatch.setattr(
        initialise.questionary,
        "text",
        lambda *args, **kwargs: _Answer(next(answers)),
    )

    initialise.init()

    assert config_path.exists()
    assert (tmp_path / ".gerbera" / "firmware").is_dir()
    assert (tmp_path / ".gerbera" / "models").is_dir()
    assert (tmp_path / ".gerbera" / "reactions").is_dir()

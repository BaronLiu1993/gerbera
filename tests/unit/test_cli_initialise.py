import pytest

from gerbera_cli.initialise import initialise


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

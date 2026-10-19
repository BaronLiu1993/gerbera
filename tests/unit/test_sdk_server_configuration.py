import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gerbera_sdk.server.configuration import SdkSettings


def test_sdk_reads_legacy_hardware_settings_without_harness_validation(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({
        "entry_point": "robot.py", "hardware_name": "robot", "devices": {},
        "harness": {"provider": "not-an-sdk-concern"},
    }))

    settings = SdkSettings.load(path)

    assert (settings.entry_point, settings.hardware_variable) == (Path("robot.py"), "robot")


def test_sdk_extracts_only_its_role_credentials_from_legacy_secret_file(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({
        "gerbera_writer_password": "writer", "gerbera_schema_password": "schema",
        "gerbera_admin_password": "admin", "api_key": "provider-key", "provider": "openai",
    }))
    settings = SdkSettings(project_root=Path("."), secrets_file=path)

    assert settings.load_secrets(tmp_path / "runtime.json").model_dump() == {
        "gerbera_writer_password": "writer", "gerbera_schema_password": "schema",
    }


@pytest.mark.parametrize("field", ["gerbera_writer_password", "gerbera_schema_password"])
def test_sdk_rejects_missing_role_credentials(tmp_path: Path, field: str) -> None:
    payload = {"gerbera_writer_password": "writer", "gerbera_schema_password": "schema"}
    payload.pop(field)
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps(payload))
    settings = SdkSettings(project_root=Path("."), secrets_file=path)

    with pytest.raises(ValidationError, match=field):
        settings.load_secrets(tmp_path / "runtime.json")


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_sdk_owns_service_port_validation(port) -> None:
    with pytest.raises(ValidationError):
        SdkSettings(port=port)


def test_sdk_initialization_does_not_overwrite_existing_hardware(monkeypatch, tmp_path: Path) -> None:
    from gerbera_sdk.server.initialise import initialise_sdk

    monkeypatch.chdir(tmp_path)
    path = tmp_path / "runtime.json"
    original = SdkSettings().model_dump_json()
    path.write_text(original)
    initialise_sdk(path)

    assert path.read_text() == original


def test_sdk_can_validate_without_cli_or_live_services(monkeypatch, tmp_path: Path, capsys) -> None:
    import sys
    from gerbera_sdk.server.__main__ import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    (tmp_path / "parts.py").write_text("ROBOT_NAME = 'standalone'\n")
    (tmp_path / "index.py").write_text(
        "from gerbera_sdk.models.hardware.hardware_system import HardwareSystem\n"
        "from parts import ROBOT_NAME\n"
        "hardware_system = HardwareSystem(name=ROBOT_NAME)\n"
    )
    (tmp_path / "secrets.json").write_text(json.dumps({
        "gerbera_writer_password": "writer", "gerbera_schema_password": "schema",
    }))
    path = tmp_path / "sdk.json"
    path.write_text(SdkSettings(project_root=Path("."), secrets_file=Path("secrets.json")).model_dump_json())
    monkeypatch.setattr("sys.argv", ["gerbera_sdk.server", "check", "--config", str(path)])

    main()

    assert json.loads(capsys.readouterr().out) == {"service": "sdk", "configuration_valid": True}


def test_sdk_validates_port_override_before_loading_hardware(monkeypatch, tmp_path: Path) -> None:
    from gerbera_sdk.server.__main__ import main

    path = tmp_path / "sdk.json"
    path.write_text(SdkSettings().model_dump_json())
    monkeypatch.setattr("sys.argv", ["gerbera_sdk.server", "serve", "--config", str(path), "--port", "0"])

    with pytest.raises(ValidationError):
        main()

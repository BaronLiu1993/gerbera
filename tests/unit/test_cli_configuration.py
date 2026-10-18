import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gerbera_cli.configuration import (
    HarnessConfig,
    ProjectConfig,
    ProjectSecrets,
)


def test_project_config_round_trips_through_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "gerbera.yaml"
    expected = ProjectConfig()

    expected.save(config_path)

    assert ProjectConfig.load(config_path) == expected


def test_project_config_migrates_legacy_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "entry_point": "robot.py",
                "hardware_name": "robot",
                "devices": {},
            }
        )
    )

    config = ProjectConfig.load(config_path)

    assert (
        config.project.entry_point,
        config.project.hardware_variable,
    ) == (Path("robot.py"), "robot")


def test_enabled_harness_requires_provider() -> None:
    with pytest.raises(ValidationError) as error:
        HarnessConfig(enabled=True)

    assert "Harness provider is required" in str(error.value)


def test_project_secrets_round_trip_without_config_file(
    tmp_path: Path,
) -> None:
    secrets_path = tmp_path / "secrets.json"
    expected = ProjectSecrets(
        gerbera_admin_password="admin",
        gerbera_schema_password="schema",
        gerbera_writer_password="writer",
        gerbera_reader_password="reader",
    )

    expected.save(secrets_path)

    assert ProjectSecrets.load(secrets_path) == expected


def test_project_secrets_accept_legacy_provider_field(
    tmp_path: Path,
) -> None:
    secrets_path = tmp_path / "secrets.json"
    secrets_path.write_text(
        json.dumps(
            {
                "provider": "openai",
                "api_key": "key",
                "gerbera_admin_password": "admin",
                "gerbera_schema_password": "schema",
                "gerbera_writer_password": "writer",
                "gerbera_reader_password": "reader",
            }
        )
    )

    secrets = ProjectSecrets.load(secrets_path)

    assert secrets.api_key == "key"

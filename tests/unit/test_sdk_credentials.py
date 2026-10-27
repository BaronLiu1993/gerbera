from pathlib import Path

import pytest

from gerbera_sdk.server.configuration import SdkSettings
from gerbera_sdk.server.credentials import initialise_credentials


@pytest.fixture
def credential_paths(tmp_path):
    config = tmp_path / "sdk.json"
    config.write_text(SdkSettings(project_root=Path("."), secrets_file=Path("sdk-secrets.json")).model_dump_json())
    return config, tmp_path / "sdk-database.env"


def test_sdk_creates_private_role_credentials_and_bootstrap_environment(credential_paths) -> None:
    config, environment = credential_paths

    initialise_credentials(config, environment)

    settings = SdkSettings.load(config)
    credentials = settings.load_secrets(config)
    secret_file = config.parent / settings.secrets_file
    expected = {
        "GERBERA_WRITER_PASSWORD": credentials.gerbera_writer_password,
        "GERBERA_SCHEMA_PASSWORD": credentials.gerbera_schema_password,
    }
    actual = dict(line.split("=", 1) for line in environment.read_text().splitlines())
    assert (actual, secret_file.stat().st_mode & 0o777, environment.stat().st_mode & 0o777) == (expected, 0o600, 0o600)


def test_repeated_sdk_initialization_preserves_credentials(credential_paths) -> None:
    config, environment = credential_paths
    initialise_credentials(config, environment)
    original = environment.read_text()

    initialise_credentials(config, environment)

    assert environment.read_text() == original


def test_sdk_rejects_conflicting_bootstrap_credentials(credential_paths) -> None:
    config, environment = credential_paths
    initialise_credentials(config, environment)
    environment.write_text("GERBERA_WRITER_PASSWORD=incorrect\n")

    with pytest.raises(ValueError, match="do not match"):
        initialise_credentials(config, environment)

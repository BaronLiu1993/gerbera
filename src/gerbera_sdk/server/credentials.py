from pathlib import Path
import secrets

from gerbera_sdk.server.configuration import SdkSecrets, SdkSettings


def write_private_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=False)
    path.write_text(content)


def initialise_credentials(config_path: Path, database_environment: Path) -> None:
    settings = SdkSettings.load(config_path)
    root = (config_path.parent / settings.project_root).resolve()
    secret_path = root / settings.secrets_file
    if secret_path.exists():
        credentials = settings.load_secrets(config_path)
    else:
        credentials = SdkSecrets(
            gerbera_writer_password=secrets.token_urlsafe(32),
            gerbera_schema_password=secrets.token_urlsafe(32),
        )
        write_private_file(secret_path, credentials.model_dump_json(indent=2))
    environment = (
        f"GERBERA_WRITER_PASSWORD={credentials.gerbera_writer_password}\n"
        f"GERBERA_SCHEMA_PASSWORD={credentials.gerbera_schema_password}\n"
    )
    if database_environment.exists():
        if database_environment.read_text() != environment:
            raise ValueError("Database bootstrap credentials do not match SDK credentials")
        return
    write_private_file(database_environment, environment)

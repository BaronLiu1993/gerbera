import json
import hashlib
from pathlib import Path
import secrets
import subprocess
import sys

import yaml


def write_secret_file(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"Secret file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=False)
    path.write_text(content)


def initialise_database_credentials() -> None:
    existing = Path(".gerbera/secrets/database.env")
    if existing.exists():
        credentials = dict(line.split("=", 1) for line in existing.read_text().splitlines() if line)
    else:
        credentials = {name: secrets.token_urlsafe(32) for name in (
            "POSTGRES_PASSWORD", "GERBERA_SCHEMA_PASSWORD", "GERBERA_WRITER_PASSWORD", "GERBERA_READER_PASSWORD",
        )}
        write_secret_file(existing, "\n".join(f"{name}={value}" for name, value in credentials.items()) + "\n")
    sdk_secret = Path(".gerbera/secrets/sdk.json")
    if not sdk_secret.exists():
        write_secret_file(sdk_secret, json.dumps({
            "gerbera_schema_password": credentials["GERBERA_SCHEMA_PASSWORD"],
            "gerbera_writer_password": credentials["GERBERA_WRITER_PASSWORD"],
        }, indent=2))
    reader_secret = Path(".gerbera/secrets/harness-database.env")
    if not reader_secret.exists():
        write_secret_file(reader_secret, f"GERBERA_READER_PASSWORD={credentials['GERBERA_READER_PASSWORD']}\n")


def initialise_project_files(with_harness: bool, provider: str | None) -> None:
    manifest = Path("gerbera.yaml")
    if manifest.exists():
        raise FileExistsError("Deployment manifest already exists; service configuration is not overwritten")
    subprocess.run([sys.executable, "-m", "gerbera_sdk.server", "initialise"], check=True)
    initialise_database_credentials()
    harness_command = [sys.executable, "-m", "gerbera_harness.initialise"]
    if provider is not None:
        harness_command.extend(("--provider", provider))
    if with_harness:
        subprocess.run(harness_command, check=True)
    manifest.write_text(yaml.safe_dump({
        "startup_timeout_seconds": 600,
        "services": {
            "database": {
                "image": "ghcr.io/baronliu1993/gerbera-postgres:latest",
                "url": "postgresql://127.0.0.1:6432", "container_port": 5432,
                "environment": {"POSTGRES_DB": "gerbera", "POSTGRES_USER": "gerbera_admin"},
                "env_files": [".gerbera/secrets/database.env"],
                "volume": f"gerbera_{hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:12]}_postgres_data",
            },
            "sdk": {
                "url": "http://127.0.0.1:8001",
                "bind_host": "0.0.0.0",
                "config": ".gerbera/sdk/runtime.json",
            },
            "harness": {
                "enabled": with_harness, "url": "http://127.0.0.1:8000",
                "image": "ghcr.io/baronliu1993/gerbera:latest",
                "config": ".gerbera/harness/harness.json", "container_port": 8000,
                "env_files": [".gerbera/secrets/harness.env", ".gerbera/secrets/harness-database.env"],
                "environment": {
                    "GERBERA_DATABASE_NAME": "gerbera", "GERBERA_READER_USER": "gerbera_reader",
                },
            },
        },
    }, sort_keys=False))

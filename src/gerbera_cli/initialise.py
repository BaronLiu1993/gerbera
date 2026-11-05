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
        return
    write_secret_file(existing, f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")


def initialise_project_files() -> None:
    manifest = Path("gerbera.yaml")
    if manifest.exists():
        raise FileExistsError("Deployment manifest already exists; service configuration is not overwritten")
    subprocess.run([sys.executable, "-m", "gerbera_sdk.server", "initialise"], check=True)
    initialise_database_credentials()
    subprocess.run([
        sys.executable, "-m", "gerbera_sdk.server", "credentials",
        "--config", ".gerbera/sdk/runtime.json", "--database-env", ".gerbera/secrets/sdk-database.env",
    ], check=True)
    manifest.write_text(yaml.safe_dump({
        "startup_timeout_seconds": 600,
        "services": {
            "database": {
                "kind": "container",
                "image": "ghcr.io/baronliu1993/gerbera-postgres:latest",
                "url": "postgresql://127.0.0.1:6432", "container_port": 5432,
                "environment": {"POSTGRES_DB": "gerbera", "POSTGRES_USER": "gerbera_admin"},
                "env_files": [".gerbera/secrets/database.env", ".gerbera/secrets/sdk-database.env"],
                "volume": f"gerbera_{hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:12]}_postgres_data",
                "volume_target": "/var/lib/postgresql/data",
            },
            "sdk": {
                "kind": "process",
                "url": "http://127.0.0.1:8001",
                "bind_host": "0.0.0.0",
                "config": ".gerbera/sdk/runtime.json",
            },
        },
    }, sort_keys=False))

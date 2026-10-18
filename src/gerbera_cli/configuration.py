import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
import yaml

from gerbera_sdk.utils import StrictSchema

PROJECT_CONFIG_PATH = Path("gerbera.yaml")
LEGACY_CONFIG_PATH = Path("config.json")
SECRETS_PATH = Path(".gerbera/secrets/secrets.json")


class RuntimeConfig(StrictSchema):
    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8001, ge=1, le=65535)
    database_host: str = Field(default="127.0.0.1", min_length=1)
    database_port: int = Field(default=6432, ge=1, le=65535)


class HarnessConfig(StrictSchema):
    enabled: bool = False
    provider: Literal["openai", "anthropic", "google", "ollama", "openai_compatible"] | None = None
    model: str | None = Field(default=None, min_length=1)
    model_type: Literal["api", "local"] = "api"
    model_endpoint: str | None = None

    @model_validator(mode="after")
    def validate_provider(self) -> "HarnessConfig":
        if self.enabled and self.provider is None:
            raise ValueError("Harness provider is required when enabled")
        return self


class ProjectSettings(StrictSchema):
    entry_point: Path = Path("index.py")
    hardware_variable: str = Field(default="hardware_system", min_length=1)


class RuntimeTransportConfig(StrictSchema):
    kind: Literal["usb_serial", "bluetooth_classic"]
    port: str = Field(min_length=1)
    device_name: str | None = None


class DeviceConfig(StrictSchema):
    id: str = Field(min_length=1)
    address: str = Field(min_length=1)
    protocol: str = Field(default="serial", min_length=1)
    fqbn: str | None = None
    runtime_transport: RuntimeTransportConfig | None = None


class ProjectConfig(StrictSchema):
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    devices: dict[str, DeviceConfig] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "ProjectConfig":
        config_path = path or find_project_config()
        data = read_config_data(config_path)
        if "project" not in data:
            data = migrate_legacy_config(data)
        return cls.model_validate(data)

    def save(self, path: Path = PROJECT_CONFIG_PATH) -> None:
        payload = self.model_dump(mode="json", exclude_none=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False))


class ProjectSecrets(StrictSchema):
    gerbera_admin_password: str = Field(min_length=1)
    gerbera_schema_password: str = Field(min_length=1)
    gerbera_writer_password: str = Field(min_length=1)
    gerbera_reader_password: str = Field(min_length=1)
    api_key: str | None = None

    @classmethod
    def load(cls, path: Path = SECRETS_PATH) -> "ProjectSecrets":
        if not path.is_file():
            raise FileNotFoundError(
                f"Gerbera secrets do not exist: {path}. Run 'gerbera init'."
            )
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"Gerbera secrets must be a mapping: {path}")
        data.pop("provider", None)
        return cls.model_validate(data)

    def save(self, path: Path = SECRETS_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True))
        path.chmod(0o600)


def find_project_config() -> Path:
    if PROJECT_CONFIG_PATH.is_file():
        return PROJECT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.is_file():
        return LEGACY_CONFIG_PATH
    raise FileNotFoundError(
        "Gerbera project configuration was not found. Run 'gerbera init'."
    )


def read_config_data(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Gerbera project configuration does not exist: {path}"
        )
    if path.suffix == ".json":
        data = json.loads(path.read_text())
    else:
        data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Gerbera project configuration must be a mapping: {path}")
    return data


def migrate_legacy_config(data: dict[str, object]) -> dict[str, object]:
    return {
        "project": {
            "entry_point": data.get("entry_point", "index.py"),
            "hardware_variable": data.get("hardware_name", "hardware_system"),
        },
        "runtime": {},
        "harness": {"enabled": False},
        "devices": data.get("devices", {}),
    }

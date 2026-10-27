from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

PROJECT_CONFIG_PATH = Path("gerbera.yaml")
ServiceName = Literal["sdk", "database", "harness"]
NonemptyString = Annotated[str, Field(min_length=1, pattern=r"\S")]


class DeploymentSpec(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, validate_default=True)

    enabled: bool = True
    url: NonemptyString

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        address = urlsplit(value)
        if not address.hostname or address.scheme not in {"http", "https", "postgresql", "postgres"}:
            raise ValueError("Service URL must specify a supported scheme and hostname")
        if address.username is not None or address.password is not None:
            raise ValueError("Service credentials belong in secret files, not service URLs")
        _ = address.port
        return value


class SdkProcessSpec(DeploymentSpec):
    kind: Literal["process"] = "process"
    config: NonemptyString
    bind_host: NonemptyString | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    env_files: tuple[str, ...] = ()

    @property
    def managed(self) -> bool:
        return True


class ContainerServiceSpec(DeploymentSpec):
    kind: Literal["container"] = "container"
    image: NonemptyString
    container_port: int = Field(ge=1, le=65535)
    environment: dict[str, str] = Field(default_factory=dict)
    env_files: tuple[str, ...] = ()
    config: NonemptyString | None = None
    config_environment: NonemptyString | None = None
    volume: NonemptyString | None = None
    volume_target: NonemptyString | None = None

    @model_validator(mode="after")
    def validate_mounts(self) -> "ContainerServiceSpec":
        if (self.config is None) != (self.config_environment is None):
            raise ValueError("Container config and config_environment must be supplied together")
        if (self.volume is None) != (self.volume_target is None):
            raise ValueError("Container volume and volume_target must be supplied together")
        if urlsplit(self.url).port is None:
            raise ValueError("Managed container URL must include its published port")
        return self

    @property
    def managed(self) -> bool:
        return True


class ExternalServiceSpec(DeploymentSpec):
    kind: Literal["external"] = "external"

    @property
    def managed(self) -> bool:
        return False


ServiceSpec = Annotated[SdkProcessSpec | ContainerServiceSpec | ExternalServiceSpec, Field(discriminator="kind")]


class ProjectConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, validate_default=True, allow_inf_nan=False)

    services: dict[ServiceName, ServiceSpec]
    startup_timeout_seconds: float = Field(default=600, gt=0)

    @model_validator(mode="after")
    def validate_service_kinds(self) -> "ProjectConfig":
        for name, service in self.services.items():
            if name == "sdk" and isinstance(service, ContainerServiceSpec):
                raise ValueError("SDK deployment must be a local process or an external service")
            if name != "sdk" and isinstance(service, SdkProcessSpec):
                raise ValueError(f"{name} deployment must be a container or an external service")
            expected = {"postgres", "postgresql"} if name == "database" else {"http", "https"}
            if urlsplit(service.url).scheme not in expected:
                raise ValueError(f"Unsupported URL scheme for {name}")
        return self

    @classmethod
    def load(cls, path: Path = PROJECT_CONFIG_PATH) -> "ProjectConfig":
        payload = yaml.safe_load(path.read_text())
        if not isinstance(payload, dict) or "services" not in payload:
            raise ValueError("Expected a deployment-only manifest with a services section")
        return cls.model_validate_json(json.dumps(payload))

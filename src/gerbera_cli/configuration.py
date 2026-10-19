from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_CONFIG_PATH = Path("gerbera.yaml")


@dataclass(frozen=True)
class ServiceSpec:
    enabled: bool = True
    managed: bool = True
    url: str = ""
    bind_host: str | None = None
    config: str | None = None
    image: str | None = None
    environment: dict[str, str] = field(default_factory=dict)
    env_files: tuple[str, ...] = ()
    volume: str | None = None
    container_port: int | None = None


@dataclass(frozen=True)
class ProjectConfig:
    services: dict[str, ServiceSpec]
    startup_timeout_seconds: float = 600

    @classmethod
    def load(cls, path: Path = PROJECT_CONFIG_PATH) -> "ProjectConfig":
        payload = yaml.safe_load(path.read_text())
        if not isinstance(payload, dict) or "services" not in payload:
            raise ValueError(
                "Expected a deployment-only manifest with a services section. "
                "Keep hardware configuration in the SDK configuration file and harness settings in its own file."
            )
        return cls(
            services={name: ServiceSpec(**spec) for name, spec in payload["services"].items()},
            startup_timeout_seconds=payload.get("startup_timeout_seconds", 600),
        )

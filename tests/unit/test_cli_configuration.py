from pathlib import Path

import pytest
import yaml

from gerbera_cli.configuration import ProjectConfig, ServiceSpec


def test_deployment_loads_only_service_metadata(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text(yaml.safe_dump({"services": {"sdk": {
        "url": "http://sdk.example:8001", "managed": False,
        "config": "not-loaded-by-cli.json",
    }}}))

    config = ProjectConfig.load(path)

    assert config.services["sdk"] == ServiceSpec(
        url="http://sdk.example:8001", managed=False, config="not-loaded-by-cli.json",
    )


def test_deployment_retains_launch_timeout(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text("services: {}\nstartup_timeout_seconds: 42\n")

    assert ProjectConfig.load(path).startup_timeout_seconds == 42


def test_legacy_domain_manifest_requires_explicit_conversion(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text("project: {}\ndevices: {}\n")

    with pytest.raises(ValueError, match="deployment-only"):
        ProjectConfig.load(path)

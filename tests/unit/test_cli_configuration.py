from pathlib import Path

import pytest
import yaml

from gerbera_cli.configuration import ContainerServiceSpec, ExternalServiceSpec, ProjectConfig, SdkProcessSpec


def test_deployment_loads_process_metadata_without_loading_hardware(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text(yaml.safe_dump({"services": {"sdk": {
        "kind": "process", "url": "http://sdk.example:8001", "config": "not-loaded-by-cli.json",
    }}}))

    config = ProjectConfig.load(path)

    assert config.services["sdk"] == SdkProcessSpec(url="http://sdk.example:8001", config="not-loaded-by-cli.json")


def test_deployment_retains_launch_timeout(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text("services: {}\nstartup_timeout_seconds: 42\n")

    assert ProjectConfig.load(path).startup_timeout_seconds == 42


def test_legacy_domain_manifest_requires_explicit_conversion(tmp_path: Path) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text("project: {}\ndevices: {}\n")

    with pytest.raises(ValueError, match="deployment-only"):
        ProjectConfig.load(path)


@pytest.mark.parametrize("spec", [
    {"url": "http://sdk.example"},
    {"kind": "external", "url": "http://sdk.example", "enabled": "false"},
    {"kind": "external", "url": "http://sdk.example", "config": "ignored.json"},
    {"kind": "process", "url": "http://sdk.example", "config": "sdk.json", "image": "ignored"},
    {"kind": "process", "url": "http://sdk.example"},
    {"kind": "container", "url": "http://sdk.example:8001", "image": "sdk", "container_port": 8001},
])
def test_deployment_rejects_missing_ambiguous_or_ignored_sdk_settings(tmp_path, spec) -> None:
    path = tmp_path / "gerbera.yaml"
    path.write_text(yaml.safe_dump({"services": {"sdk": spec}}))

    with pytest.raises(ValueError):
        ProjectConfig.load(path)


@pytest.mark.parametrize("changes", [
    {"container_port": 0}, {"image": ""}, {"volume": "data"}, {"config": "harness.json"},
    {"url": "postgresql://localhost"},
])
def test_container_configuration_is_complete_and_validated(changes) -> None:
    payload = {"url": "postgresql://localhost:6432", "image": "postgres", "container_port": 5432} | changes

    with pytest.raises(ValueError):
        ContainerServiceSpec(**payload)


@pytest.mark.parametrize("timeout", [0, float("inf")])
def test_deployment_rejects_unbounded_or_nonpositive_timeout(timeout) -> None:
    with pytest.raises(ValueError):
        ProjectConfig(services={}, startup_timeout_seconds=timeout)


def test_external_service_has_no_local_execution_settings() -> None:
    assert ExternalServiceSpec(url="http://remote.example").managed is False

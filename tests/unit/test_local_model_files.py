from pathlib import Path

import pytest
import yaml

from gerbera_sdk.inference.models.neural_network import local_model_files
from gerbera_sdk.inference.models.neural_network.local_model_files import (
    LocalModelFiles,
)


@pytest.fixture
def models_path(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "models"
    path.mkdir()
    monkeypatch.setattr(local_model_files, "MODELS_PATH", path)
    return path


def test_reads_manifest_from_named_model_subfolder(models_path: Path) -> None:
    model_directory = models_path / "detector"
    model_directory.mkdir()
    manifest = {"schema_version": 1, "weights": "model.onnx"}
    (model_directory / "model.yaml").write_text(yaml.safe_dump(manifest))

    assert LocalModelFiles("detector").read_manifest() == manifest


@pytest.mark.parametrize(
    "directory_name",
    ["", ".", "..", "../outside", "/absolute", "nested/model"],
)
def test_rejects_model_directories_outside_models_path(
    models_path: Path,
    directory_name: str,
) -> None:
    with pytest.raises(ValueError, match="one subfolder name"):
        LocalModelFiles(directory_name).directory


def test_rejects_model_directory_symlink_outside_models_path(
    models_path: Path,
    tmp_path: Path,
) -> None:
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (models_path / "linked").symlink_to(outside_directory, target_is_directory=True)

    with pytest.raises(ValueError, match="remain inside"):
        LocalModelFiles("linked").directory


def test_missing_manifest_fails_explicitly(models_path: Path) -> None:
    (models_path / "detector").mkdir()

    with pytest.raises(FileNotFoundError, match="manifest does not exist"):
        LocalModelFiles("detector").read_manifest()


def test_manifest_must_be_a_mapping(models_path: Path) -> None:
    model_directory = models_path / "detector"
    model_directory.mkdir()
    (model_directory / "model.yaml").write_text("- invalid\n- manifest\n")

    with pytest.raises(ValueError, match="must contain a mapping"):
        LocalModelFiles("detector").read_manifest()


def test_malformed_manifest_fails_explicitly(models_path: Path) -> None:
    model_directory = models_path / "detector"
    model_directory.mkdir()
    (model_directory / "model.yaml").write_text("weights: [unterminated")

    with pytest.raises(yaml.YAMLError):
        LocalModelFiles("detector").read_manifest()


def test_missing_weights_fail_explicitly(models_path: Path) -> None:
    (models_path / "detector").mkdir()

    with pytest.raises(FileNotFoundError, match="weights do not exist"):
        LocalModelFiles("detector").weights_path("model.onnx")


def test_rejects_weights_outside_model_directory(models_path: Path) -> None:
    (models_path / "detector").mkdir()

    with pytest.raises(ValueError, match="remain inside"):
        LocalModelFiles("detector").weights_path("../model.onnx")

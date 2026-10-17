from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from gerbera_sdk.paths import MODELS_PATH

MODEL_MANIFEST_FILENAME = "model.yaml"


@dataclass(frozen=True)
class LocalModelFiles:
    directory_name: str

    @property
    def directory(self) -> Path:
        relative_directory = Path(self.directory_name)
        if (
            not self.directory_name
            or relative_directory.is_absolute()
            or len(relative_directory.parts) != 1
            or relative_directory.name in {".", ".."}
        ):
            raise ValueError(
                "Model directory must be one subfolder name under "
                f"{MODELS_PATH}: {self.directory_name!r}"
            )
        models_directory = MODELS_PATH.resolve()
        directory = (MODELS_PATH / relative_directory).resolve()
        if not directory.is_relative_to(models_directory):
            raise ValueError(
                f"Model directory must remain inside {MODELS_PATH}: "
                f"{self.directory_name!r}"
            )
        return directory

    @property
    def manifest_path(self) -> Path:
        path = self.directory / MODEL_MANIFEST_FILENAME
        if not path.is_file():
            raise FileNotFoundError(f"Model manifest does not exist: {path}")
        return path

    def read_manifest(self) -> dict[str, Any]:
        manifest = yaml.safe_load(self.manifest_path.read_text())
        if not isinstance(manifest, dict):
            raise ValueError(
                f"Model manifest must contain a mapping: {self.manifest_path}"
            )
        return manifest

    def weights_path(self, filename: str) -> Path:
        relative_path = Path(filename)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(
                f"Model weights must remain inside {self.directory}: {filename}"
            )

        model_directory = self.directory
        path = (self.directory / relative_path).resolve()
        if not path.is_relative_to(model_directory):
            raise ValueError(
                f"Model weights must remain inside {self.directory}: {filename}"
            )
        if not path.is_file():
            raise FileNotFoundError(f"Model weights do not exist: {path}")
        return path

from pathlib import Path


GERBERA_PATH = Path(".gerbera")
FIRMWARE_PATH = GERBERA_PATH / "firmware"
MODELS_PATH = GERBERA_PATH / "models"
REACTIONS_PATH = GERBERA_PATH / "reactions"


def create_project_directories(project_root: Path = Path(".")) -> None:
    (project_root / FIRMWARE_PATH).mkdir(parents=True, exist_ok=True)
    (project_root / MODELS_PATH).mkdir(parents=True, exist_ok=True)
    (project_root / REACTIONS_PATH).mkdir(parents=True, exist_ok=True)

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("config.json")


def _load_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"{config_path} not found")

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{config_path} is not valid JSON") from exc

    if not isinstance(config, dict):
        raise ValueError(f"{config_path} must contain a JSON object")

    return config

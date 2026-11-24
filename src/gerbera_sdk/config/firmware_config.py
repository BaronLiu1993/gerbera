from importlib.resources import files

import yaml


FIRMWARE_CONFIGURATION = {
    "led": "led.yaml",
    "dcmotor": "dcmotor.yaml",
    "hcsr04": "hcsr04.yaml",
    "hw201": "hw201.yaml",
    "ky033": "ky033.yaml",
    "mg996r": "mg996r.yaml",
    "sg90": "sg90.yaml",
}


def load_firmware_config(component_type: str) -> dict:
    filename = FIRMWARE_CONFIGURATION[component_type]
    path = files("gerbera_sdk.config").joinpath("firmware", filename)
    return yaml.safe_load(path.read_text(encoding="utf-8"))

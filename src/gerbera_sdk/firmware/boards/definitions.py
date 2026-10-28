from importlib import resources

from gerbera_sdk.configuration_io import decode_yaml
from gerbera_sdk.firmware.boards.config_schema import BoardConfigurations
from gerbera_sdk.firmware.boards.strategies import (
    BoardDefinition,
    BoardPinDefinition,
    BoardRegistry,
    build_board_definition,
)


def load_board_registry() -> BoardRegistry:
    config_resource = resources.files("gerbera_sdk.firmware.boards").joinpath("config.yaml")
    config = BoardConfigurations.from_data(decode_yaml(config_resource.read_text()))
    return BoardRegistry({board.fqbn: build_board_definition(board) for board in config.boards})


BOARD_REGISTRY = load_board_registry()
ARDUINO_UNO = BOARD_REGISTRY.get_definition("arduino:avr:uno")
ARDUINO_MEGA = BOARD_REGISTRY.get_definition("arduino:avr:mega")
ESP32_DEV_MODULE = BOARD_REGISTRY.get_definition("esp32:esp32:esp32")

__all__ = [
    "ARDUINO_MEGA",
    "ARDUINO_UNO",
    "BOARD_REGISTRY",
    "ESP32_DEV_MODULE",
    "BoardDefinition",
    "BoardPinDefinition",
    "BoardRegistry",
    "build_board_definition",
]

from importlib import resources

import yaml

from gerbera_sdk.firmware.boards.config_schema import AvrBoardConfig, BoardConfigurations

from gerbera_sdk.firmware.boards.strategies import (
    AvrBoardDefinitionStrategy,
    BoardDefinition,
    BoardDefinitionStrategy,
    BoardPinDefinition,
    BoardRegistry,
    Esp32DevModuleDefinitionStrategy,
)


def load_board_strategies() -> tuple[BoardDefinitionStrategy, ...]:
    config_resource = resources.files("gerbera_sdk.firmware.boards").joinpath(
        "config.yaml"
    )
    config = BoardConfigurations.from_data(yaml.safe_load(config_resource.read_text()))
    return tuple(
        AvrBoardDefinitionStrategy.from_config(board)
        if isinstance(board, AvrBoardConfig)
        else Esp32DevModuleDefinitionStrategy.from_config(board)
        for board in config.boards
    )


BOARD_STRATEGIES = load_board_strategies()
BOARD_DEFINITIONS = tuple(strategy.build() for strategy in BOARD_STRATEGIES)
BOARD_REGISTRY = BoardRegistry(BOARD_DEFINITIONS)
STRATEGIES_BY_FQBN = {
    strategy.fqbn: strategy for strategy in BOARD_STRATEGIES
}

ARDUINO_UNO_STRATEGY = STRATEGIES_BY_FQBN["arduino:avr:uno"]
ARDUINO_MEGA_STRATEGY = STRATEGIES_BY_FQBN["arduino:avr:mega"]
ESP32_DEV_MODULE_STRATEGY = STRATEGIES_BY_FQBN["esp32:esp32:esp32"]

ARDUINO_UNO = BOARD_REGISTRY.get_definition("arduino:avr:uno")
ARDUINO_MEGA = BOARD_REGISTRY.get_definition("arduino:avr:mega")
ESP32_DEV_MODULE = BOARD_REGISTRY.get_definition("esp32:esp32:esp32")

__all__ = [
    "ARDUINO_MEGA",
    "ARDUINO_MEGA_STRATEGY",
    "ARDUINO_UNO",
    "ARDUINO_UNO_STRATEGY",
    "BOARD_REGISTRY",
    "ESP32_DEV_MODULE",
    "ESP32_DEV_MODULE_STRATEGY",
    "BoardDefinition",
    "BoardPinDefinition",
    "BoardRegistry",
]

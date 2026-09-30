from collections.abc import Callable, Mapping
from importlib import resources
from typing import Any

import yaml

from gerbera_sdk.firmware.boards.strategies import (
    AvrBoardDefinitionStrategy,
    BoardDefinition,
    BoardDefinitionStrategy,
    BoardPinDefinition,
    BoardRegistry,
    Esp32DevModuleDefinitionStrategy,
)

StrategyLoader = Callable[[Mapping[str, Any]], BoardDefinitionStrategy]
STRATEGY_LOADERS: Mapping[str, StrategyLoader] = {
    "avr": AvrBoardDefinitionStrategy.from_data,
    "esp32_dev_module": Esp32DevModuleDefinitionStrategy.from_data,
}


def load_board_strategies() -> tuple[BoardDefinitionStrategy, ...]:
    config_resource = resources.files("gerbera_sdk.firmware.boards").joinpath(
        "config.yaml"
    )
    config = yaml.safe_load(config_resource.read_text())
    return tuple(
        STRATEGY_LOADERS[board["strategy"]](board)
        for board in config["boards"]
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

from dataclasses import dataclass, field
from importlib import resources

import yaml
from gerbera_sdk.firmware.boards.config_schema import BoardConfig, BoardConfigurations
from gerbera_sdk.firmware.firmware_schema import BoardTransportKind, PinCapability



@dataclass(frozen=True)
class BoardPinDefinition:
    canonical_name: str
    aliases: frozenset[str]
    capabilities: frozenset[PinCapability]
    reserved_by: str | None = None


@dataclass
class BoardDefinition:
    fqbn: str
    pins: tuple[BoardPinDefinition, ...]
    includes: tuple[str, ...]
    libraries: tuple[str, ...]
    supported_transports: frozenset[BoardTransportKind] = frozenset(
        {BoardTransportKind.USB_SERIAL}
    )
    pins_by_alias: dict[str, BoardPinDefinition] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.pins_by_alias = {alias: pin for pin in self.pins for alias in pin.aliases}

    def resolve_pin(self, pin_name: str) -> BoardPinDefinition:
        try:
            return self.pins_by_alias[pin_name]
        except KeyError as exc:
            raise ValueError(f"Unknown physical pin for {self.fqbn}: {pin_name}") from exc


@dataclass
class BoardRegistry:
    definitions: dict[str, BoardDefinition]

    def get_definition(self, fqbn: str) -> BoardDefinition:
        try:
            return self.definitions[fqbn]
        except KeyError as exc:
            raise ValueError(f"Unsupported microcontroller fqbn: {fqbn}") from exc


def build_board_definition(config: BoardConfig) -> BoardDefinition:
    return BoardDefinition(
        fqbn=config.fqbn,
        pins=tuple(
            BoardPinDefinition(
                canonical_name=pin.canonical_name,
                aliases=frozenset(pin.aliases),
                capabilities=frozenset(pin.capabilities),
                reserved_by=pin.reserved_by,
            )
            for pin in config.pins
        ),
        includes=config.includes,
        libraries=config.libraries,
        supported_transports=frozenset(config.supported_transports),
    )


def load_board_registry() -> BoardRegistry:
    config_resource = resources.files("gerbera_sdk.firmware.boards").joinpath("config.yaml")
    config = BoardConfigurations.from_data(yaml.safe_load(config_resource.read_text()))
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

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from gerbera_sdk.firmware.firmware_schema import PinCapability


@dataclass(frozen=True)
class BoardPinDefinition:
    canonical_name: str
    aliases: frozenset[str]
    capabilities: frozenset[PinCapability]
    reserved_by: str | None = None


@dataclass(frozen=True)
class BoardDefinition:
    fqbn: str
    pins: tuple[BoardPinDefinition, ...]
    includes: tuple[str, ...]
    libraries: tuple[str, ...]
    pins_by_alias: Mapping[str, BoardPinDefinition] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        pins_by_alias: dict[str, BoardPinDefinition] = {}
        for pin in self.pins:
            for alias in pin.aliases:
                if alias in pins_by_alias:
                    raise ValueError(
                        f"Duplicate pin alias for {self.fqbn}: {alias}"
                    )
                pins_by_alias[alias] = pin
        object.__setattr__(
            self,
            "pins_by_alias",
            MappingProxyType(pins_by_alias),
        )

    def resolve_pin(self, pin_name: str) -> BoardPinDefinition:
        try:
            return self.pins_by_alias[pin_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown physical pin for {self.fqbn}: {pin_name}"
            ) from exc


@dataclass(frozen=True)
class BoardRegistry:
    definitions: tuple[BoardDefinition, ...]
    definitions_by_fqbn: Mapping[str, BoardDefinition] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        definitions_by_fqbn: dict[str, BoardDefinition] = {}
        for definition in self.definitions:
            if definition.fqbn in definitions_by_fqbn:
                raise ValueError(f"Duplicate board FQBN: {definition.fqbn}")
            definitions_by_fqbn[definition.fqbn] = definition
        object.__setattr__(
            self,
            "definitions_by_fqbn",
            MappingProxyType(definitions_by_fqbn),
        )

    def get_definition(self, fqbn: str) -> BoardDefinition:
        try:
            return self.definitions_by_fqbn[fqbn]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported microcontroller fqbn: {fqbn}"
            ) from exc


_DIGITAL_CAPABILITIES = frozenset(
    {
        PinCapability.DIGITAL_INPUT,
        PinCapability.DIGITAL_OUTPUT,
    }
)
_ANALOG_CAPABILITIES = _DIGITAL_CAPABILITIES | {
    PinCapability.ANALOG_INPUT,
}


def _digital_pin(
    pin: int,
    *,
    pwm: bool = False,
    interrupt: bool = False,
    reserved_by: str | None = None,
) -> BoardPinDefinition:
    capabilities = set(_DIGITAL_CAPABILITIES)
    if pwm:
        capabilities.add(PinCapability.PWM_OUTPUT)
    if interrupt:
        capabilities.add(PinCapability.INTERRUPT_INPUT)
    return BoardPinDefinition(
        canonical_name=str(pin),
        aliases=frozenset({str(pin), f"D{pin}"}),
        capabilities=frozenset(capabilities),
        reserved_by=reserved_by,
    )


def _analog_pin(pin: int, digital_alias: int) -> BoardPinDefinition:
    return BoardPinDefinition(
        canonical_name=f"A{pin}",
        aliases=frozenset({f"A{pin}", str(digital_alias)}),
        capabilities=frozenset(_ANALOG_CAPABILITIES),
    )


ARDUINO_UNO = BoardDefinition(
    fqbn="arduino:avr:uno",
    pins=tuple(
        _digital_pin(
            pin,
            pwm=pin in {3, 5, 6, 9, 10, 11},
            interrupt=pin in {2, 3},
            reserved_by="serial" if pin in {0, 1} else None,
        )
        for pin in range(14)
    )
    + tuple(_analog_pin(pin, pin + 14) for pin in range(6)),
    includes=("Arduino.h",),
    libraries=("arduino:avr",),
)


ARDUINO_MEGA = BoardDefinition(
    fqbn="arduino:avr:mega",
    pins=tuple(
        _digital_pin(
            pin,
            pwm=pin in set(range(2, 14)) | {44, 45, 46},
            interrupt=pin in {2, 3, 18, 19, 20, 21},
            reserved_by="serial" if pin in {0, 1} else None,
        )
        for pin in range(54)
    )
    + tuple(_analog_pin(pin, pin + 54) for pin in range(16)),
    includes=("Arduino.h",),
    libraries=("arduino:avr",),
)


BOARD_REGISTRY = BoardRegistry((ARDUINO_MEGA, ARDUINO_UNO))

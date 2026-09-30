from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Protocol

from gerbera_sdk.firmware.firmware_schema import (
    BoardTransportKind,
    PinCapability,
)


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
    supported_transports: frozenset[BoardTransportKind] = frozenset(
        {BoardTransportKind.USB_SERIAL}
    )
    pins_by_alias: Mapping[str, BoardPinDefinition] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pins_by_alias",
            MappingProxyType(
                {
                    alias: pin
                    for pin in self.pins
                    for alias in pin.aliases
                }
            ),
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
        object.__setattr__(
            self,
            "definitions_by_fqbn",
            MappingProxyType(
                {
                    definition.fqbn: definition
                    for definition in self.definitions
                }
            ),
        )

    def get_definition(self, fqbn: str) -> BoardDefinition:
        try:
            return self.definitions_by_fqbn[fqbn]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported microcontroller fqbn: {fqbn}"
            ) from exc


class BoardDefinitionStrategy(Protocol):
    def build(self) -> BoardDefinition: ...


@dataclass(frozen=True)
class AvrBoardDefinitionStrategy:
    fqbn: str
    digital_pin_count: int
    analog_pin_count: int
    pwm_pins: frozenset[int]
    interrupt_pins: frozenset[int]
    includes: tuple[str, ...] = ("Arduino.h",)
    libraries: tuple[str, ...] = ("arduino:avr",)
    supported_transports: frozenset[BoardTransportKind] = frozenset(
        {BoardTransportKind.USB_SERIAL}
    )

    serial_pins: ClassVar[frozenset[int]] = frozenset({0, 1})
    digital_capabilities: ClassVar[frozenset[PinCapability]] = frozenset(
        {
            PinCapability.DIGITAL_INPUT,
            PinCapability.DIGITAL_OUTPUT,
        }
    )
    analog_capabilities: ClassVar[frozenset[PinCapability]] = (
        digital_capabilities | {PinCapability.ANALOG_INPUT}
    )

    @classmethod
    def from_data(
        cls,
        data: Mapping[str, Any],
    ) -> "AvrBoardDefinitionStrategy":
        return cls(
            fqbn=data["fqbn"],
            digital_pin_count=data["digital_pin_count"],
            analog_pin_count=data["analog_pin_count"],
            pwm_pins=frozenset(data["pwm_pins"]),
            interrupt_pins=frozenset(data["interrupt_pins"]),
            includes=tuple(data["includes"]),
            libraries=tuple(data["libraries"]),
            supported_transports=frozenset(
                BoardTransportKind(kind)
                for kind in data["supported_transports"]
            ),
        )

    def build(self) -> BoardDefinition:
        digital_pins = tuple(
            self.build_digital_pin(pin)
            for pin in range(self.digital_pin_count)
        )
        analog_pins = tuple(
            self.build_analog_pin(pin)
            for pin in range(self.analog_pin_count)
        )
        return BoardDefinition(
            fqbn=self.fqbn,
            pins=digital_pins + analog_pins,
            includes=self.includes,
            libraries=self.libraries,
            supported_transports=self.supported_transports,
        )

    def build_digital_pin(self, pin: int) -> BoardPinDefinition:
        capabilities = set(self.digital_capabilities)
        if pin in self.pwm_pins:
            capabilities.add(PinCapability.PWM_OUTPUT)
        if pin in self.interrupt_pins:
            capabilities.add(PinCapability.INTERRUPT_INPUT)
        return BoardPinDefinition(
            canonical_name=str(pin),
            aliases=frozenset({str(pin), f"D{pin}"}),
            capabilities=frozenset(capabilities),
            reserved_by="serial" if pin in self.serial_pins else None,
        )

    def build_analog_pin(self, pin: int) -> BoardPinDefinition:
        digital_alias = pin + self.digital_pin_count
        return BoardPinDefinition(
            canonical_name=f"A{pin}",
            aliases=frozenset({f"A{pin}", str(digital_alias)}),
            capabilities=self.analog_capabilities,
        )


@dataclass(frozen=True)
class Esp32DevModuleDefinitionStrategy:
    fqbn: str
    includes: tuple[str, ...]
    libraries: tuple[str, ...]
    output_pins: tuple[int, ...]
    input_only_pins: tuple[int, ...]
    analog_input_pins: frozenset[int]
    reserved_pins: Mapping[int, str]
    flash_pins: tuple[int, ...]
    supported_transports: frozenset[BoardTransportKind]

    output_capabilities: ClassVar[frozenset[PinCapability]] = frozenset(
        {
            PinCapability.DIGITAL_INPUT,
            PinCapability.DIGITAL_OUTPUT,
            PinCapability.PWM_OUTPUT,
            PinCapability.INTERRUPT_INPUT,
        }
    )
    input_capabilities: ClassVar[frozenset[PinCapability]] = frozenset(
        {
            PinCapability.DIGITAL_INPUT,
            PinCapability.INTERRUPT_INPUT,
        }
    )

    @classmethod
    def from_data(
        cls,
        data: Mapping[str, Any],
    ) -> "Esp32DevModuleDefinitionStrategy":
        return cls(
            fqbn=data["fqbn"],
            includes=tuple(data["includes"]),
            libraries=tuple(data["libraries"]),
            output_pins=tuple(data["output_pins"]),
            input_only_pins=tuple(data["input_only_pins"]),
            analog_input_pins=frozenset(data["analog_input_pins"]),
            reserved_pins=MappingProxyType(
                {
                    int(pin): reason
                    for pin, reason in data["reserved_pins"].items()
                }
            ),
            flash_pins=tuple(data["flash_pins"]),
            supported_transports=frozenset(
                BoardTransportKind(kind)
                for kind in data["supported_transports"]
            ),
        )

    def build(self) -> BoardDefinition:
        output_pins = tuple(
            self.build_output_pin(pin) for pin in self.output_pins
        )
        input_pins = tuple(
            self.build_input_pin(pin) for pin in self.input_only_pins
        )
        flash_pins = tuple(
            self.build_flash_pin(pin) for pin in self.flash_pins
        )
        return BoardDefinition(
            fqbn=self.fqbn,
            pins=output_pins + input_pins + flash_pins,
            includes=self.includes,
            libraries=self.libraries,
            supported_transports=self.supported_transports,
        )

    def build_output_pin(self, pin: int) -> BoardPinDefinition:
        return self.build_pin(
            pin,
            self.output_capabilities,
        )

    def build_input_pin(self, pin: int) -> BoardPinDefinition:
        return self.build_pin(pin, self.input_capabilities)

    def build_flash_pin(self, pin: int) -> BoardPinDefinition:
        return self.build_pin(pin, self.output_capabilities)

    def build_pin(
        self,
        pin: int,
        capabilities: frozenset[PinCapability],
    ) -> BoardPinDefinition:
        pin_capabilities = capabilities
        if pin in self.analog_input_pins:
            pin_capabilities |= {PinCapability.ANALOG_INPUT}
        return BoardPinDefinition(
            canonical_name=str(pin),
            aliases=frozenset({str(pin), f"D{pin}", f"GPIO{pin}"}),
            capabilities=pin_capabilities,
            reserved_by=self.reserved_pins.get(pin),
        )

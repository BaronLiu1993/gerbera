from typing import Annotated, Literal

from pydantic import Field, model_validator

from gerbera_sdk.firmware.firmware_schema import BoardTransportKind
from gerbera_sdk.utils import StrictSchema

NonemptyString = Annotated[str, Field(min_length=1, pattern=r"\S")]
PinNumber = Annotated[int, Field(ge=0)]


class BoardConfig(StrictSchema):
    fqbn: NonemptyString
    includes: tuple[NonemptyString, ...]
    libraries: tuple[NonemptyString, ...]
    supported_transports: tuple[BoardTransportKind, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transports(self):
        if len(set(self.supported_transports)) != len(self.supported_transports):
            raise ValueError("Duplicate board transport")
        return self


class AvrBoardConfig(BoardConfig):
    strategy: Literal["avr"]
    digital_pin_count: int = Field(gt=0)
    analog_pin_count: int = Field(ge=0)
    pwm_pins: tuple[PinNumber, ...]
    interrupt_pins: tuple[PinNumber, ...]

    @model_validator(mode="after")
    def validate_pin_numbers(self):
        for pins in (self.pwm_pins, self.interrupt_pins):
            if len(set(pins)) != len(pins) or any(pin >= self.digital_pin_count for pin in pins):
                raise ValueError("AVR pin lists must contain unique declared digital pins")
        return self


class Esp32BoardConfig(BoardConfig):
    strategy: Literal["esp32_dev_module"]
    output_pins: tuple[PinNumber, ...]
    input_only_pins: tuple[PinNumber, ...]
    analog_input_pins: tuple[PinNumber, ...]
    reserved_pins: dict[int, NonemptyString]
    flash_pins: tuple[PinNumber, ...]

    @model_validator(mode="after")
    def validate_pin_numbers(self):
        groups = (self.output_pins, self.input_only_pins, self.analog_input_pins, self.flash_pins)
        if any(len(set(pins)) != len(pins) for pins in groups):
            raise ValueError("Duplicate ESP32 pin")
        if set(self.output_pins) & set(self.input_only_pins):
            raise ValueError("ESP32 output and input-only pins must be distinct")
        return self


BoardStrategyConfig = Annotated[AvrBoardConfig | Esp32BoardConfig, Field(discriminator="strategy")]


class BoardConfigurations(StrictSchema):
    boards: tuple[BoardStrategyConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identities(self):
        identities = [board.fqbn for board in self.boards]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate board FQBN")
        return self

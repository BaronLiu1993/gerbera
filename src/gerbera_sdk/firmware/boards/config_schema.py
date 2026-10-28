from typing import Annotated

from pydantic import Field, model_validator

from gerbera_sdk.firmware.firmware_schema import BoardTransportKind, PinCapability
from gerbera_sdk.utils import StrictSchema

NonemptyString = Annotated[str, Field(min_length=1, pattern=r"\S")]


class PinConfig(StrictSchema):
    canonical_name: NonemptyString
    aliases: tuple[NonemptyString, ...] = Field(min_length=1)
    capabilities: tuple[PinCapability, ...] = Field(min_length=1)
    reserved_by: str | None = None


class BoardConfig(StrictSchema):
    fqbn: NonemptyString
    includes: tuple[NonemptyString, ...]
    libraries: tuple[NonemptyString, ...]
    supported_transports: tuple[BoardTransportKind, ...] = Field(min_length=1)
    pins: tuple[PinConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transports(self):
        if len(set(self.supported_transports)) != len(self.supported_transports):
            raise ValueError("Duplicate board transport")
        return self


class BoardConfigurations(StrictSchema):
    boards: tuple[BoardConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identities(self):
        identities = [board.fqbn for board in self.boards]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate board FQBN")
        return self

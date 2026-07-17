from abc import ABC, abstractmethod

from gerbera_sdk.contracts.command_contract import CommandSpec
from gerbera_sdk.contracts.firmware_contract import LibrarySpec, PinModeSpec
from gerbera_sdk.models.hardware.connection import Connection


class BaseFirmwareBuilder(ABC):
    template_name: str = ""

    def required_libraries(self) -> list[LibrarySpec]:
        return []

    # Optional hook for devices that need global runtime objects.
    def build_definitions(self, connection: Connection) -> str:
        return ""

    # Optional hook for devices that need setup beyond pinMode(...).
    def build_setup_lines(self, connection: Connection) -> list[str]:
        return []

    @abstractmethod
    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        raise NotImplementedError

    @abstractmethod
    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        raise NotImplementedError

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

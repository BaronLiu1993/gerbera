from abc import ABC, abstractmethod

from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.firmware_schema import CommandSpec
from gerbera_sdk.firmware.firmware_schema import (
    ColumnSpec,
    LibrarySpec,
    PinModeSpec,
    StreamContract,
)
from gerbera_sdk.models.hardware.connection import Connection


class BaseFirmwareBuilder(ABC):
    supports_streaming: bool = False

    # Optional, depending on the device
    # Optional hook for devices that need global runtime objects.
    def build_definitions(self, connection: Connection) -> str:
        return ""

    # Optional hook for devices that need setup beyond pinMode(...).
    def build_setup_lines(self, connection: Connection) -> list[str]:
        return []

    # Optional hook for devices that need recurring loop behavior.
    def build_stream_lines(self, connection: Connection) -> list[str]:
        return []

    # Optional hook for stream table schema. Key is column name.
    def stream_schema(self, connection: Connection) -> dict[str, ColumnSpec]:
        return {}

    def build_stream_contract(
        self,
        connection: Connection,
    ) -> StreamContract | None:
        if not connection.stream_enabled:
            return None

        if not self.supports_streaming:
            raise ValueError(
                f"{connection.component_type} does not support streaming"
            )

        return StreamContract(
            event_name=connection.event_name,
            table_name=connection.event_name,
            schema=self.stream_schema(connection),
            connection=connection,
        )


    # All Required to Implement
    @abstractmethod
    def required_libraries(self) -> list[LibrarySpec]:
        raise NotImplementedError

    @abstractmethod
    def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
        raise NotImplementedError

    @abstractmethod
    def required_commands(self, connection: Connection) -> list[CommandSpec]:
        raise NotImplementedError

    @abstractmethod
    def annotations(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> ToolAnnotations:
        raise NotImplementedError

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

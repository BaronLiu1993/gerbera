from abc import ABC, abstractmethod

from gerbera_sdk.models.connection import Connection


class BaseFirmwareBuilder(ABC):
    template_name: str = ""

    def required_libraries(self) -> list[dict[str, str]]:
        return []

    def pin_modes(self, connection: Connection) -> dict[str, str]:
        return {
            str(pin): "INPUT"
            for pin in (connection.pins or {}).values()
        }

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

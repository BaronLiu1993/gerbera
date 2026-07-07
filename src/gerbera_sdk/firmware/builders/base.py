from abc import ABC, abstractmethod

from gerbera_sdk.hardware.connection import Connection


class BaseFirmwareBuilder(ABC):
    template_name: str = ""

    def build_includes(self) -> list[str]:
        return []

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

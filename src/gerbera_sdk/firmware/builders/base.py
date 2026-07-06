from abc import ABC, abstractmethod

from gerbera_sdk.hardware.connections import Connection


class BaseFirmwareBuilder(ABC):
    template_name: str = ""

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

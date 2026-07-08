from abc import ABC, abstractmethod

from gerbera_sdk.models.connection import Connection


class BaseFirmwareBuilder(ABC):
    template_name: str = ""

    def required_libraries(self) -> list[dict[str, str]]:
        return []

    @abstractmethod
    def build_handler(self, connection: Connection) -> str:
        raise NotImplementedError

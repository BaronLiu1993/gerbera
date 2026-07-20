from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime


class GerberaServer:
    def __init__(self, hardware_system: HardwareSystem) -> None:
        self.runtime = ServerRuntime(hardware_system)

    @property
    def app(self):
        return self.runtime.app

    def run(
        self,
        transport: str = "stdio",
        **transport_kwargs,
    ) -> None:
        self.runtime.run(
            transport=transport,
            **transport_kwargs,
        )

    def close(self) -> None:
        self.runtime.close()

import subprocess

from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.models.runtime.server import GerberaServer
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


class GerberaRuntime:
    @staticmethod
    def install_dependencies(hardware_system: HardwareSystem) -> None:
        for package_name in hardware_system.get_required_microcontroller_packages():
            subprocess.run(
                ["arduino-cli", "core", "install", package_name],
                check=True,
            )

        installed_libraries: set[str] = set()
        for microcontroller in hardware_system.microcontrollers:
            for library in microcontroller.get_required_libraries():
                install_name = library.install.strip()
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_install_name)

    @staticmethod
    def setup(
        hardware_system: HardwareSystem,
        install_dependencies: bool = True,
        flash_firmware: bool = True,
    ) -> None:
        if install_dependencies:
            GerberaRuntime.install_dependencies(hardware_system)

        if flash_firmware:
            Flash.flash(hardware_system)

    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str = "stdio",
        **transport_kwargs,
    ) -> None:
        server = GerberaServer(hardware_system)

        try:
            server.run(
                transport=transport,
                **transport_kwargs,
            )
        finally:
            server.close()

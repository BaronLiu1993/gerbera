import subprocess

from gerbera_sdk.firmware.function.flash import Flash
from gerbera_sdk.mcp.server import GerberaMCPServer
from gerbera_sdk.models.hardware_system import HardwareSystem


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
                install_name = library.get("install", "").strip()
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_install_name)

    @staticmethod
    def create_server(
        hardware_system: HardwareSystem
    ) -> GerberaMCPServer:
        GerberaRuntime.install_dependencies(hardware_system)
        Flash.flash(hardware_system)
        return GerberaMCPServer(hardware_system)

    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        install_dependencies: bool = True,
        flash_firmware: bool = True,
    ) -> None:
        server = GerberaRuntime.create_server(
            hardware_system=hardware_system,
            install_dependencies=install_dependencies,
            flash_firmware=flash_firmware,
        )

        try:
            server.run()
        finally:
            server.close()

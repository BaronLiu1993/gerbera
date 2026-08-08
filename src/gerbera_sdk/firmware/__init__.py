"""Firmware generation and flashing."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gerbera_sdk.firmware.flash import Flash
    from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator

__all__ = [
    "Flash",
    "FirmwareGenerator",
]


def __getattr__(name: str):
    if name == "Flash":
        from gerbera_sdk.firmware.flash import Flash

        return Flash
    if name == "FirmwareGenerator":
        from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator

        return FirmwareGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

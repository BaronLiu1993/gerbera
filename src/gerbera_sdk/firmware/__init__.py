"""Firmware generation and flashing."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gerbera_sdk.firmware.flash import Flash
    from gerbera_sdk.firmware.generator import Generator

__all__ = [
    "Flash",
    "Generator",
]


def __getattr__(name: str):
    if name == "Flash":
        from gerbera_sdk.firmware.flash import Flash

        return Flash
    if name == "Generator":
        from gerbera_sdk.firmware.generator import Generator

        return Generator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

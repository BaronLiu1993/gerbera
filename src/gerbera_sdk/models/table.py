from dataclasses import dataclass

from gerbera_sdk.contracts.firmware_contract import ColumnSpec


@dataclass(frozen=True)
class Table:
    name: str
    schema: dict[str, ColumnSpec]

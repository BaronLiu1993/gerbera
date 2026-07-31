from dataclasses import dataclass, field

from gerbera_sdk.contracts.firmware_contract import ColumnSpec

@dataclass(frozen=True)
class Table:
    name: str
    schema: dict[str, ColumnSpec]


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str
    table_names: dict[str, Table] = field(default_factory=dict)

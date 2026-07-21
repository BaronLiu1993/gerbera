from dataclasses import dataclass, field

from gerbera_sdk.models.hardware.table import Table


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str
    table_names: dict[str, Table] = field(default_factory=dict)

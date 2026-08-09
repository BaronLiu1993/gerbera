from dataclasses import dataclass, field

@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str
    table_names: list[str] = field(default_factory=dict)

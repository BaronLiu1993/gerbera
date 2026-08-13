from dataclasses import dataclass, field

import psycopg
from psycopg import Connection


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str
    table_names: dict[str, str] = field(default_factory=dict)

    def connect(self) -> Connection:
        return psycopg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.databaseName,
        )

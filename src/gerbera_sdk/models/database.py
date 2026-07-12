from dataclasses import dataclass, field
import psycopg
from psycopg import sql


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    database: str
    buffer_size: int = 100


    def to_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Database":
        return cls(
            host=str(payload.get("host")),
            port=int(payload.get("port")),
            user=str(payload.get("user")),
            password=str(payload.get("password")),
            database=str(payload.get("database")),
        )

from dataclasses import dataclass


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    database: str

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
            host=str(payload.get("host", "127.0.0.1")),
            port=int(payload.get("port", 5432)),
            user=str(payload.get("user", "postgres")),
            password=str(payload.get("password", "")),
            database=str(payload.get("database", "gerbera")),
        )

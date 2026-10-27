from dataclasses import dataclass, field

from gerbera_sdk.models.hardware.database import Database


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    writer_password: str = field(repr=False)
    schema_password: str | None = field(default=None, repr=False)

    def writer(self) -> Database:
        return Database(
            host=self.host, port=self.port, password=self.writer_password,
            user="gerbera_writer", database_name="gerbera",
        )

    def schema_owner(self) -> Database | None:
        if self.schema_password is None:
            return None
        return Database(
            host=self.host, port=self.port, password=self.schema_password,
            user="gerbera_schema_owner", database_name="gerbera",
        )

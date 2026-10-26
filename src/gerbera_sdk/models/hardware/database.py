from typing import Annotated

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass
import psycopg
from psycopg import sql


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True))
class Database:
    host: Annotated[str, Field(min_length=1, pattern=r"\S")]
    port: Annotated[int, Field(ge=1, le=65535)]
    user: Annotated[str, Field(min_length=1, pattern=r"\S")]
    password: Annotated[str, Field(min_length=1)]
    database_name: Annotated[str, Field(min_length=1, pattern=r"\S")]

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        if not payload:
            raise ValueError(f"Database write payload is empty: {table_name}")

        keys = payload[0].keys()
        query = sql.SQL(
            "INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(", ").join(sql.Placeholder(key) for key in keys),
        )

        with psycopg.connect(self.dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, payload)

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.database_name} "
            f"user={self.user} "
            f"password={self.password}"
        )

from dataclasses import dataclass, field
import uuid

import psycopg
from psycopg import sql

from gerbera_sdk.contracts.firmware_contract import ColumnSpec
from gerbera_sdk.models.table import Table


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str
    hardware_system_id: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_names: dict[str, Table] = field(default_factory=dict)

    def _dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.databaseName} "
            f"user={self.user} "
            f"password={self.password}"
        )

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, object]],
    ) -> None:
        if not payload:
            return

        keys = payload[0].keys()
        query = sql.SQL(
            "INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(", ").join(sql.Placeholder(k) for k in keys),
        )

        with psycopg.connect(self._dsn()) as conn:
            with conn.cursor() as cur:
                cur.executemany(query, payload)
            conn.commit()

    def create_database_table(
        self,
        table_name: str,
        schema: dict[str, ColumnSpec],
    ) -> None:
        if table_name in self.table_names:
            return

        column_defs: list[sql.SQL] = []
        index_statements: list[sql.SQL] = []

        for column_name, column_spec in schema.items():
            parts = [
                sql.Identifier(column_name),
                sql.SQL(column_spec.type.value),
            ]

            if column_spec.sql_suffix is not None:
                parts.append(sql.SQL(column_spec.sql_suffix))

            if column_spec.default is not None:
                parts.append(sql.SQL("DEFAULT "))
                parts.append(sql.SQL(column_spec.default))

            if column_spec.primary_key:
                parts.append(sql.SQL("PRIMARY KEY"))

            if not column_spec.nullable:
                parts.append(sql.SQL("NOT NULL"))

            column_defs.append(sql.SQL(" ").join(parts))

            if column_spec.idx:
                index_name = f"{table_name}_{column_name}_idx"
                index_statements.append(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
                    ).format(
                        index_name=sql.Identifier(index_name),
                        table_name=sql.Identifier(table_name),
                        column_name=sql.Identifier(column_name),
                    )
                )

        create_table_query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(column_defs),
        )

        with psycopg.connect(self._dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)

                for index_query in index_statements:
                    cur.execute(index_query)

            conn.commit()
        
        self.table_names[table_name] = Table(table_name, schema) 

    def to_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.databaseName,
            "hardware_system_id": self.hardware_system_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Database":
        return cls(
            host=str(payload.get("host")),
            port=int(payload.get("port")),
            user=str(payload.get("user")),
            password=str(payload.get("password")),
            databaseName=str(payload.get("database")),
            hardware_system_id=str(payload.get("hardware_system_id", "")),
        )

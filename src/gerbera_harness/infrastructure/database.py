from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

JsonPrimitive = str | int | float | bool | None


@dataclass
class DatabaseGateway:
    host: str
    port: str
    db_name: str
    read_user: str
    read_password: str
    timeout: float = 30.0

    def read_dsn(self) -> str:
        return (
            f"dbname={self.db_name} "
            f"user={self.read_user} "
            f"password={self.read_password} "
            f"host={self.host} "
            f"port={self.port}"
        )

    async def execute_query(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(
            self.read_dsn(),
            connect_timeout=self.timeout,
        ) as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute("SET LOCAL statement_timeout = '10s'")

                async with conn.cursor() as cur:
                    await cur.execute(query)

                    columns = [column.name for column in cur.description]
                    rows = await cur.fetchall()

        return [
            {
                column: self.json_safe_value(value)
                for column, value in zip(columns, row, strict=True)
            }
            for row in rows
        ]

    async def get_table_schemas(
        self,
        table_names: list[str],
    ) -> list[dict[str, Any]]:
        if not table_names:
            return []

        async with await AsyncConnection.connect(
            self.read_dsn(),
            connect_timeout=self.timeout,
        ) as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute("SET LOCAL statement_timeout = '10s'")
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        select
                            table_name,
                            column_name as name,
                            data_type as type
                        from information_schema.columns
                        where table_schema = 'public'
                          and table_name = any(%s)
                        order by table_name, ordinal_position
                        """,
                        (table_names,),
                    )

                    columns = [column.name for column in cur.description]
                    raw_rows = await cur.fetchall()

        rows = [dict(zip(columns, row, strict=True)) for row in raw_rows]

        schemas_by_table = {
            table_name: {"table_name": table_name, "columns": []}
            for table_name in table_names
        }
        for row in rows:
            schemas_by_table[row["table_name"]]["columns"].append(
                {
                    "name": row["name"],
                    "type": row["type"],
                }
            )

        return list(schemas_by_table.values())

    @staticmethod
    def json_safe_value(value: Any) -> JsonPrimitive | list[Any] | dict[str, Any]:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, datetime | date | time):
            return value.isoformat()
        if isinstance(value, Decimal | UUID):
            return str(value)
        if isinstance(value, list | tuple):
            return [DatabaseGateway.json_safe_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): DatabaseGateway.json_safe_value(item)
                for key, item in value.items()
            }
        return str(value)

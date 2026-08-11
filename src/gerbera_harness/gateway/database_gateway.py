from dataclasses import dataclass
from functools import cached_property
from typing import Any

from psycopg_pool import AsyncConnectionPool


# Create this object with the read only user role credentials only
# Connect with read only database users ONLY
# Create sql gateway user and then the main one has the main gerbera user for writing tables
@dataclass
class DatabaseGateway:
    host: str
    port: str
    db_name: str
    user: str
    password: str
    timeout: float = 30.0
    min_size: int = 5
    max_size: int = 20

    @cached_property
    def connection_pool(self):
        conninfo = (
            f"dbname={self.db_name} "
            f"user={self.user} "
            f"password={self.password} "
            f"host={self.host} "
            f"port={self.port}"
        )

        return AsyncConnectionPool(
            conninfo=conninfo,
            timeout=self.timeout,
            min_size=self.min_size,
            max_size=self.max_size,
            open=False,
        )

    # No need to check queries, we have DB level user permissioning with read roles
    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        pool = await self.open_connection_pool()

        async with pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute("SET LOCAL statement_timeout = '10s'")

                async with conn.cursor() as cur:
                    await cur.execute(query, params)

                    columns = [column.name for column in cur.description]
                    rows = await cur.fetchall()

        return [dict(zip(columns, row, strict=True)) for row in rows]

    async def open_connection_pool(self) -> AsyncConnectionPool:
        if self.connection_pool.closed:
            await self.connection_pool.open()

        return self.connection_pool

    async def get_table_schema(self, table_name: str) -> dict:
        rows = await self.execute_query(
            """
            select
                column_name as name,
                data_type as type
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %(table_name)s
            order by ordinal_position
            """,
            {"table_name": table_name},
        )
        return {
            "table_name": table_name,
            "columns": rows,
        }

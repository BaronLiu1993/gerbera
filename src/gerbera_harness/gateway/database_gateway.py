from psycopg_pool import AsyncConnectionPool
from dataclasses import dataclass
from functools import cached_property


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
        )

    # No need to check queries, we have DB level user permissioning with read roles
    async def execute_query(self, query: str) -> list[dict]:
        async with self.connection_pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute("SET LOCAL statement_timeout = '10s'")

                async with conn.cursor() as cur:
                    await cur.execute(query)

                    columns = [column.name for column in cur.description]
                    rows = await cur.fetchall()

        return [dict(zip(columns, row, strict=True)) for row in rows]

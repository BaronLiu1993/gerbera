from psycopg_pool import AsyncConnectionPool
from dataclasses import dataclass
from functools import cached_property

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

    async def run_query(self, query: str):
        async with self.connection_pool() as conn:
            conn.execute("BEGIN READ ONLY")
            async with conn.cursor() as cur:
                await cur.execute(query)
                columns = [column.name for column in cur.description]
                rows = await cur.fetchall()
            conn.commit()

        results = []
        for row in rows:
            results.append(dict(zip(columns, row, strict=True)))

        return results
        
        
        

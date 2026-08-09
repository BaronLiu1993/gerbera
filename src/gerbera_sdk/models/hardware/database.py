from dataclasses import dataclass


@dataclass
class Database:
    host: str
    port: int
    user: str
    password: str
    databaseName: str

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        if not payload:
            raise ValueError(f"Database write payload is empty: {table_name}")

        import psycopg
        from psycopg import sql

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
            f"dbname={self.databaseName} "
            f"user={self.user} "
            f"password={self.password}"
        )

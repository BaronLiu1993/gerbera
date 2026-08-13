import asyncio
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from gerbera_harness.infrastructure.database import DatabaseGateway


class FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeCursor:
    description = [
        FakeColumn("table_name"),
        FakeColumn("name"),
        FakeColumn("type"),
    ]

    def __init__(self) -> None:
        self.query: str | None = None
        self.params: tuple[list[str]] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def execute(self, query: str, params: tuple[list[str]]) -> None:
        self.query = query
        self.params = params

    async def fetchall(self) -> list[tuple[str, str, str]]:
        return [
            ("readings", "created_at", "timestamp without time zone"),
            ("readings", "value", "integer"),
            ("events", "id", "uuid"),
        ]


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.executed: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str) -> None:
        self.executed.append(query)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class FakePool:
    def __init__(self) -> None:
        self.opened = False
        self.connection_instance = FakeConnection()

    async def open(self) -> None:
        self.opened = True

    def connection(self) -> FakeConnection:
        return self.connection_instance


class FakeDatabaseGateway(DatabaseGateway):
    def __init__(self) -> None:
        self.pool = FakePool()

    @property
    def connection_pool(self) -> FakePool:
        return self.pool


def test_get_table_schemas_uses_parameterized_schema_query() -> None:
    gateway = FakeDatabaseGateway()

    result = asyncio.run(
        gateway.get_table_schemas(["readings", "events"])
    )

    cursor = gateway.connection_pool.connection_instance.cursor_instance

    assert gateway.connection_pool.opened is True
    assert "table_name = any(%s)" in cursor.query
    assert cursor.params == (["readings", "events"],)
    assert result == [
        {
            "table_name": "readings",
            "columns": [
                {
                    "name": "created_at",
                    "type": "timestamp without time zone",
                },
                {"name": "value", "type": "integer"},
            ],
        },
        {
            "table_name": "events",
            "columns": [{"name": "id", "type": "uuid"}],
        },
    ]


def test_get_table_schemas_returns_empty_list_without_querying() -> None:
    gateway = FakeDatabaseGateway()

    assert asyncio.run(gateway.get_table_schemas([])) == []
    assert gateway.connection_pool.opened is False


def test_database_gateway_returns_json_safe_values() -> None:
    assert DatabaseGateway.json_safe_value(
        {
            "created_at": datetime(2026, 8, 11, 23, 13, 49),
            "run_date": date(2026, 8, 11),
            "run_time": time(23, 13, 49),
            "ratio": Decimal("0.95"),
            "stable": True,
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "values": [1, datetime(2026, 8, 11, 23, 13, 50)],
        }
    ) == {
        "created_at": "2026-08-11T23:13:49",
        "run_date": "2026-08-11",
        "run_time": "23:13:49",
        "ratio": "0.95",
        "stable": True,
        "id": "12345678-1234-5678-1234-567812345678",
        "values": [1, "2026-08-11T23:13:50"],
    }

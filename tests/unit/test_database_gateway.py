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


class FakeAsyncConnection:
    connection_instance = FakeConnection()

    @classmethod
    async def connect(cls, dsn: str, *, connect_timeout: float):
        return cls.connection_instance


def database_gateway() -> DatabaseGateway:
    return DatabaseGateway(
        host="database.internal",
        port="5432",
        db_name="gerbera",
        read_user="reader",
        read_password="secret",
    )


def test_get_table_schemas_uses_parameterized_schema_query(monkeypatch) -> None:
    FakeAsyncConnection.connection_instance = FakeConnection()
    monkeypatch.setattr(
        "gerbera_harness.infrastructure.database.AsyncConnection",
        FakeAsyncConnection,
    )
    gateway = database_gateway()

    result = asyncio.run(
        gateway.get_table_schemas(["readings", "events"])
    )

    connection = FakeAsyncConnection.connection_instance
    cursor = connection.cursor_instance

    assert connection.executed == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '10s'",
    ]
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
    gateway = database_gateway()

    assert asyncio.run(gateway.get_table_schemas([])) == []


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

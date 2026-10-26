from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest

from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.runtime.storage.storage import RuntimeStorage, connect_database


@pytest.fixture
def database():
    return Database(host="database", port=5432, user="writer", password="test", database_name="gerbera")


def test_sdk_retries_only_database_connection_failures(monkeypatch, database) -> None:
    connection = object()
    connect = Mock(side_effect=[psycopg.OperationalError("starting"), connection])
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.psycopg.connect", connect)
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.time.sleep", lambda seconds: None)

    assert connect_database(database) is connection


def test_sdk_database_wait_has_a_deadline(monkeypatch, database) -> None:
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.psycopg.connect",
                        Mock(side_effect=psycopg.OperationalError("not available")))
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.time.monotonic", Mock(side_effect=[0, 61]))

    with pytest.raises(TimeoutError, match="storage"):
        connect_database(database)


def test_schema_errors_are_not_retried_as_readiness_failures(monkeypatch, database) -> None:
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.psycopg.connect",
                        Mock(side_effect=psycopg.ProgrammingError("invalid schema")))

    with pytest.raises(psycopg.ProgrammingError):
        connect_database(database)


def test_no_streams_require_no_schema_privileges(database) -> None:
    RuntimeStorage(SimpleNamespace(boards=[]), database).prepare()


def test_sdk_prepares_schema_as_owner_before_checking_writer(monkeypatch, database) -> None:
    owner = Database(host="database", port=5432, user="schema_owner", password="test", database_name="gerbera")
    contract = SimpleNamespace(table_name="sensor", schema={})
    plan = SimpleNamespace(boards=[SimpleNamespace(connections=[SimpleNamespace(component_type="sensor")])])
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=None)
    connection = SimpleNamespace(cursor=lambda: cursor, execute=Mock())
    roles = []
    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.get_device_builder",
                        lambda kind: SimpleNamespace(build_stream_contract=lambda item: contract))

    def connect(role):
        roles.append(role.user)
        return nullcontext(connection)

    monkeypatch.setattr("gerbera_sdk.models.runtime.storage.storage.connect_database", connect)

    RuntimeStorage(plan, database, owner).prepare()

    assert roles == ["schema_owner", "writer"]

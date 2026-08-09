import pytest

from gerbera_sdk.models.hardware.database import Database


def _database() -> Database:
    return Database("localhost", 5432, "user", "password", "gerbera")


def test_database_builds_dsn() -> None:
    assert _database().dsn() == (
        "host=localhost "
        "port=5432 "
        "dbname=gerbera "
        "user=user "
        "password=password"
    )


def test_database_rejects_empty_writes() -> None:
    with pytest.raises(ValueError, match="payload is empty"):
        _database().write_database_table("readings", [])

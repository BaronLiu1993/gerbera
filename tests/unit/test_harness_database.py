from gerbera_harness.infrastructure.legacy_database import Database


def test_connect_uses_database_configuration(monkeypatch) -> None:
    connection = object()
    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return connection

    monkeypatch.setattr(
        "gerbera_harness.infrastructure.legacy_database.psycopg.connect",
        fake_connect,
    )
    database = Database(
        host="database.example.com",
        port=5432,
        user="gerbera",
        password="secret",
        databaseName="experiments",
    )

    assert database.connect() is connection
    assert calls == [
        {
            "host": "database.example.com",
            "port": 5432,
            "user": "gerbera",
            "password": "secret",
            "dbname": "experiments",
        }
    ]

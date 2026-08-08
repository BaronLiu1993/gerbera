from dataclasses import dataclass, field

import psycopg
from psycopg import sql

from gerbera_sdk.contracts.firmware_contract import ColumnSpec, ColumnType
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.firmware.configurations import get_device_builder
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.database import Table
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem

FRAMES_TABLE_NAME = "frames"
FRAMES_TABLE_SCHEMA: dict[str, ColumnSpec] = {
    "id": ColumnSpec(
        type=ColumnType.TEXT,
        primary_key=True,
        nullable=False,
    ),
    "base64_string": ColumnSpec(
        type=ColumnType.TEXT,
        nullable=False,
    ),
    "camera_name": ColumnSpec(
        type=ColumnType.TEXT,
        idx=True,
        nullable=False,
    ),
    "timestamp": ColumnSpec(
        type=ColumnType.TIMESTAMP,
        idx=True,
        nullable=False,
        default="CURRENT_TIMESTAMP",
    ),
}


@dataclass
class DatabaseRuntime:
    hardware_system: HardwareSystem
    event_worker: EventWorker
    database: Database | None = None
    _registered_tables: set[str] = field(default_factory=set)

    def start(self) -> None:
        self._create_tables()
        if not self._registered_tables:
            return

        self.event_worker.configure_writer(self)
        self.event_worker.start()

    def stop(self) -> None:
        if not self._registered_tables:
            return

        try:
            self.event_worker.wait_until_idle()
        finally:
            self.event_worker.stop()

    def write_database_table(
        self,
        table_name: str,
        payload: list[dict[str, str]],
    ) -> None:
        if not payload:
            return

        if table_name not in self._registered_tables:
            raise RuntimeError(f"Database table is not registered: {table_name}")

        database = self._runtime_database()
        if database is None:
            raise RuntimeError("Database runtime is not configured")

        keys = payload[0].keys()
        query = sql.SQL(
            "INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, keys)),
            placeholders=sql.SQL(", ").join(sql.Placeholder(key) for key in keys),
        )

        with psycopg.connect(self._dsn(database)) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, payload)

    def _create_tables(self) -> None:
        database = self._runtime_database()
        if database is None:
            return

        self._create_database_table(
            database,
            FRAMES_TABLE_NAME,
            FRAMES_TABLE_SCHEMA,
        )
        self._registered_tables.add(FRAMES_TABLE_NAME)

        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                builder = get_device_builder(connection.component_type)
                contract = builder.build_stream_contract(connection)
                if contract is None:
                    continue

                self._create_database_table(
                    database,
                    contract.table_name,
                    contract.schema,
                )
                self._registered_tables.add(contract.table_name)

    def _runtime_database(self) -> Database | None:
        if self.database is not None:
            return self.database

        legacy_databases = [
            connection.database
            for microcontroller in self.hardware_system.microcontrollers
            for connection in microcontroller.connections
            if connection.database is not None
        ]
        if not legacy_databases:
            return None

        database = legacy_databases[0]
        if any(candidate != database for candidate in legacy_databases[1:]):
            raise ValueError("DatabaseRuntime supports one database per run")
        return database

    def create_table(
        self,
        table_name: str,
        schema: dict[str, ColumnSpec],
    ) -> None:
        database = self._runtime_database()
        if database is None:
            raise RuntimeError("Database runtime is not configured")

        self._create_database_table(database, table_name, schema)
        self._registered_tables.add(table_name)

    def _create_database_table(
        self,
        database: Database,
        table_name: str,
        schema: dict[str, ColumnSpec],
    ) -> None:
        if table_name in database.table_names:
            return

        column_definitions: list[sql.Composed] = []
        index_statements: list[sql.Composed] = []

        for column_name, column_spec in schema.items():
            parts = [
                sql.Identifier(column_name),
                sql.SQL(column_spec.type.value),
            ]

            if column_spec.sql_suffix is not None:
                parts.append(sql.SQL(column_spec.sql_suffix))
            if column_spec.default is not None:
                parts.extend([sql.SQL("DEFAULT "), sql.SQL(column_spec.default)])
            if column_spec.primary_key:
                parts.append(sql.SQL("PRIMARY KEY"))
            if not column_spec.nullable:
                parts.append(sql.SQL("NOT NULL"))

            column_definitions.append(sql.SQL(" ").join(parts))

            if column_spec.idx:
                index_statements.append(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {index_name} "
                        "ON {table_name} ({column_name})"
                    ).format(
                        index_name=sql.Identifier(
                            f"{table_name}_{column_name}_idx"
                        ),
                        table_name=sql.Identifier(table_name),
                        column_name=sql.Identifier(column_name),
                    )
                )

        create_table_query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
        ).format(
            table_name=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(column_definitions),
        )

        with psycopg.connect(self._dsn(database)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
                for index_query in index_statements:
                    cursor.execute(index_query)

        database.table_names[table_name] = Table(table_name, schema)

    @staticmethod
    def _dsn(database: Database) -> str:
        return (
            f"host={database.host} "
            f"port={database.port} "
            f"dbname={database.databaseName} "
            f"user={database.user} "
            f"password={database.password}"
        )

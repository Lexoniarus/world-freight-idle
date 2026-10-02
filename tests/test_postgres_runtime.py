"""PostgreSQL/Supabase adapter regression tests without a live database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import psycopg
import pytest
from psycopg.pq import TransactionStatus
from psycopg_pool import PoolTimeout

from app.bootstrap import (
    build_game_database,
    build_vehicle_catalogue,
    build_world_catalogue,
)
from app.config import Settings
from app.domain.errors import (
    CatalogueError,
    PersistenceError,
    UnsupportedGameSchema,
    WorldCatalogueError,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.postgres_catalogues import (
    PostgresVehicleCatalogue,
    PostgresWorldCatalogue,
    _catalogue_conninfo,
)
from app.repositories.postgres_database import (
    _RUNTIME_TABLES,
    HybridRow,
    PostgresConnectionAdapter,
    PostgresCursorAdapter,
    PostgresGameDatabase,
    require_schema_name,
    translate_sql,
)


class FakeCursor:
    """Small psycopg cursor double used at the adapter boundary."""

    def __init__(self, connection, rows=(), names=(), rowcount=1):
        self.connection = connection
        self.rows = list(rows)
        self.description: Any = tuple(
            SimpleNamespace(name=name) for name in names
        )
        self.rowcount = rowcount
        self.executed = []

    def execute(self, statement, parameters=()):
        self.executed.append((statement, parameters))
        self.connection.executed.append((statement, parameters))
        configured = self.connection.responses(statement, parameters)
        if configured is not None:
            rows, names = configured
            self.rows = list(rows)
            self.description = tuple(
                SimpleNamespace(name=name) for name in names
            )
        return self

    def executemany(self, statement, parameters):
        self.executed.append((statement, tuple(parameters)))
        self.connection.executed.append((statement, tuple(parameters)))
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def __iter__(self):
        return iter(self.rows)


class FakeConnection:
    """Connection double covering pool, transaction and cursor behavior."""

    def __init__(self, responses=None):
        self.autocommit = True
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self._responses = responses or (lambda statement, parameters: None)

    def responses(self, statement, parameters):
        return self._responses(statement, parameters)

    def cursor(self):
        return FakeCursor(self)

    def execute(self, statement, parameters=()):
        self.executed.append((statement, parameters))
        if statement.startswith("BEGIN"):
            self.info.transaction_status = TransactionStatus.INTRANS
        elif statement in {"COMMIT", "ROLLBACK"}:
            self.info.transaction_status = TransactionStatus.IDLE
        return FakeCursor(self).execute(statement, parameters)

    def commit(self):
        self.commits += 1
        self.info.transaction_status = TransactionStatus.IDLE

    def rollback(self):
        self.rollbacks += 1
        self.info.transaction_status = TransactionStatus.IDLE

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePool:
    """ConnectionPool double with one reusable raw connection."""

    connection_instance: Any = None

    def __init__(self, *args, **kwargs):
        del args, kwargs
        self.raw = self.connection_instance or FakeConnection()
        self.closed = False

    @contextmanager
    def connection(self):
        yield self.raw

    def close(self):
        self.closed = True


def make_settings(tmp_path, database_url=None):
    return Settings(
        base_dir=tmp_path,
        data_dir=tmp_path,
        db_path=tmp_path / "game.db",
        nominatim_url="https://nominatim.example",
        valhalla_url="https://valhalla.example",
        http_user_agent="tests",
        valhalla_client_id="tests",
        request_timeout_seconds=1,
        game_time_scale=1,
        log_level="INFO",
        database_url=database_url,
    )


def translated(statement: str) -> str:
    result = translate_sql(statement)
    assert result is not None
    return result


def test_postgres_sql_translation_contract():
    assert require_schema_name("world_catalogue") == "world_catalogue"
    with pytest.raises(ValueError):
        require_schema_name("game;drop")
    assert translate_sql("PRAGMA foreign_keys=ON") is None
    assert translate_sql("CREATE TABLE x(a TEXT)") is None
    assert "information_schema.tables" in translated(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    assert translate_sql("BEGIN IMMEDIATE") == "BEGIN"
    assert "auth_attempts.attempts + 1" in translated(
        """INSERT INTO auth_attempts VALUES (?, 1, ?)
        ON CONFLICT(bucket) DO UPDATE SET
            attempts = auth_attempts.attempts + 1
        RETURNING attempts"""
    )
    assert translated("SELECT * FROM x WHERE a=?").endswith("a=%s")
    assert "LIKE 'https://%%'" in translated(
        "SELECT * FROM x WHERE url LIKE 'https://%'"
    )
    assert "::integer" in translated("SELECT SUM(status='idle') FROM x")
    assert "jsonb_array_elements_text" in translated(
        "SELECT * FROM market_templates WHERE city_uid IN "
        "(SELECT value FROM json_each(?)) ORDER BY rowid"
    )
    assert "ORDER BY template_id" in translated(
        "SELECT * FROM market_templates ORDER BY rowid"
    )
    assert "ORDER BY vehicle_id" in translated(
        "SELECT * FROM owned_vehicles ORDER BY rowid"
    )
    assert "ORDER BY created_at, contract_id" in translated(
        "SELECT * FROM contract_offers ORDER BY rowid"
    )
    assert "ORDER BY departed_at, transport_id" in translated(
        "SELECT * FROM transports ORDER BY rowid"
    )
    with pytest.raises(ValueError):
        translate_sql("SELECT * FROM unknown ORDER BY rowid")
    assert "::bigint" in translated(
        "SELECT json_extract(x, '$.version') FROM t"
    )
    assert "double precision" in translated(
        "SELECT json_extract(x, '$.data.route.distance_km') FROM t"
    )
    assert "NULLIF" in translated(
        "SELECT json_extract(x, '$.data.destination') FROM t"
    )
    assert "#>>" in translated("SELECT json_extract(x, '$.kind') FROM t")
    assert "'integer'" in translated("SELECT json_type(x, '$.version') FROM t")
    assert "'real'" in translated(
        "SELECT json_type(x, '$.data.contract.tons') FROM t"
    )


def test_postgres_row_contract():
    row = HybridRow(("first", "second"), (1, "two"))
    assert row.keys() == ("first", "second")
    assert row[0] == 1 and row["second"] == "two"
    assert list(row) == [1, "two"]
    assert len(row) == 2
    assert dict(row) == {"first": 1, "second": "two"}


def test_postgres_cursor_contract():
    raw = FakeConnection()
    cursor = FakeCursor(raw, [(1, "a"), (2, "b")], ("id", "name"), 2)
    adapter = PostgresCursorAdapter(cursor)
    assert adapter.rowcount == 2
    first = adapter.fetchone()
    assert first is not None and first["name"] == "a"
    assert [row[0] for row in adapter.fetchall()] == [2]
    empty = PostgresCursorAdapter()
    assert empty.rowcount == 0
    assert empty.fetchone() is None
    assert empty.fetchall() == []
    assert list(empty) == []


def test_postgres_connection_adapter_contract():
    raw = FakeConnection()
    adapter = PostgresConnectionAdapter(raw)
    assert adapter.execute("PRAGMA query_only=ON").fetchone() is None
    cursor = adapter.execute("SELECT ? AS value", (3,))
    assert raw.executed[-1][0] == "SELECT %s AS value"
    assert cursor.rowcount == 1
    adapter.executemany("INSERT INTO x VALUES (?)", ((1,), (2,)))
    adapter.executescript("CREATE TABLE ignored(value TEXT);")
    adapter.commit()
    adapter.rollback()
    raw.info.transaction_status = TransactionStatus.INTRANS
    adapter.commit()
    raw.info.transaction_status = TransactionStatus.INTRANS
    adapter.rollback()
    assert any(item[0] == "COMMIT" for item in raw.executed)
    assert any(item[0] == "ROLLBACK" for item in raw.executed)


def test_postgres_adapter_failure_contracts():
    with pytest.raises(ValueError):
        translate_sql("SELECT json_extract(payload, '$') FROM snapshots")

    raw = FakeConnection()
    cursor = FakeCursor(raw)
    cursor.description = None
    adapter = PostgresCursorAdapter(cursor)
    assert adapter.fetchone() is None
    assert list(adapter) == []

    connection = PostgresConnectionAdapter(raw)
    assert connection.executemany("PRAGMA foreign_keys=ON", ()).rowcount == 0
    raw.autocommit = False
    raw.info.transaction_status = TransactionStatus.INTRANS
    connection.commit()
    raw.info.transaction_status = TransactionStatus.INTRANS
    connection.rollback()
    assert raw.commits == 1
    assert raw.rollbacks == 1

    class IntegrityCursor(FakeCursor):
        def execute(self, statement, parameters=()):
            del statement, parameters
            raise psycopg.IntegrityError("constraint")

        def executemany(self, statement, parameters):
            del statement, parameters
            raise psycopg.IntegrityError("constraint")

    raw.cursor = lambda: IntegrityCursor(raw)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO x VALUES (?)", (1,))
    with pytest.raises(sqlite3.IntegrityError):
        connection.executemany("INSERT INTO x VALUES (?)", ((1,),))


def test_postgres_database_lifecycle(monkeypatch):
    required = {
        "account_emails",
        "account_preferences",
        "auth_attempts",
        "contract_offers",
        "game_schema",
        "geocode_cache",
        "market_coverage",
        "market_offer_templates",
        "market_preparations",
        "market_stock_cursors",
        "market_stock_pending",
        "market_template_uses",
        "market_templates",
        "offer_route_references",
        "owned_vehicles",
        "player_states",
        "route_cache",
        "routing_anchor_sources",
        "routing_anchors",
        "routing_attempts",
        "routing_connection_proofs",
        "routing_leases",
        "routing_provider_revisions",
        "routing_relations",
        "sessions",
        "transports",
        "users",
    }

    def responses(statement, parameters):
        del parameters
        if "information_schema.tables" in statement:
            return ([(name,) for name in sorted(required)], ("table_name",))
        if "SELECT version FROM game_schema" in statement:
            return ([("1.2.0",)], ("version",))
        if "FROM pg_indexes" in statement:
            return ([("CREATE UNIQUE INDEX ...",)], ("indexdef",))
        if "pg_get_triggerdef" in statement:
            return ([("CREATE TRIGGER ...",)], ("pg_get_triggerdef",))
        return ([], ())

    raw = FakeConnection(responses)
    FakePool.connection_instance = raw
    monkeypatch.setattr(
        "app.repositories.postgres_database.ConnectionPool", FakePool
    )
    database = PostgresGameDatabase("postgresql://example/db", pool_size=2)
    database.initialize()
    with database.connect() as connection:
        assert isinstance(connection, PostgresConnectionAdapter)
    with database.read_transaction():
        with database.connect() as nested:
            assert isinstance(nested, PostgresConnectionAdapter)
    with database.transaction():
        with database.connect() as nested:
            assert isinstance(nested, PostgresConnectionAdapter)
    assert any("pg_advisory_xact_lock" in item[0] for item in raw.executed)
    database.close()
    assert database._pool.closed
    FakePool.connection_instance = None


def test_postgres_database_failure_contracts(monkeypatch):
    monkeypatch.setattr(
        "app.repositories.postgres_database.ConnectionPool", FakePool
    )
    raw = FakeConnection()
    FakePool.connection_instance = raw
    database = PostgresGameDatabase("postgresql://example/db")

    with database.read_transaction():
        with database.read_transaction():
            pass
    with database.transaction():
        with database.transaction():
            pass
    with pytest.raises(RuntimeError):
        with database.transaction():
            raise RuntimeError("rollback")
    assert raw.rollbacks >= 2

    class FailingPool:
        @contextmanager
        def connection(self):
            raise PoolTimeout("timeout")
            yield

    database._pool = cast(Any, FailingPool())
    with pytest.raises(PersistenceError):
        with database.connect():
            pass
    with pytest.raises(PersistenceError):
        with database.read_transaction():
            pass
    with pytest.raises(PersistenceError):
        with database.transaction():
            pass
    FakePool.connection_instance = None


@pytest.mark.parametrize(
    ("version", "index_rows", "trigger_rows", "error_text"),
    (
        (None, (), (), "unvollständig"),
        ("0.0.0", (("index",),), (("trigger",),), "version"),
        ("1.2.0", (), (("trigger",),), "schutz"),
    ),
)
def test_postgres_schema_validation_failures(
    monkeypatch, version, index_rows, trigger_rows, error_text
):
    def responses(statement, parameters):
        del parameters
        if "information_schema.tables" in statement:
            tables = _RUNTIME_TABLES if version is not None else ()
            return ([(name,) for name in sorted(tables)], ("table_name",))
        if "SELECT version FROM game_schema" in statement:
            return ([(version,)], ("version",))
        if "FROM pg_indexes" in statement:
            return (index_rows, ("indexdef",))
        if "pg_get_triggerdef" in statement:
            return (trigger_rows, ("pg_get_triggerdef",))
        return ([], ())

    FakePool.connection_instance = FakeConnection(responses)
    monkeypatch.setattr(
        "app.repositories.postgres_database.ConnectionPool", FakePool
    )
    database = PostgresGameDatabase("postgresql://example/db")
    with pytest.raises(UnsupportedGameSchema, match=error_text):
        database.initialize()
    FakePool.connection_instance = None


def test_postgres_catalogue_connection_contract(monkeypatch):
    assert "search_path=world_catalogue,public" in _catalogue_conninfo(
        "postgresql://example/db", "world_catalogue"
    )
    raw = FakeConnection()

    @contextmanager
    def fake_connect(*args, **kwargs):
        del args, kwargs
        yield raw

    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.psycopg.connect", fake_connect
    )
    sentinel = object()
    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.read_world_snapshot",
        lambda connection: sentinel,
    )
    world = PostgresWorldCatalogue("postgresql://example/db")
    assert world.read() is sentinel

    def vehicle_responses(statement, parameters):
        del parameters
        if "catalog_metadata" in statement:
            return ([("2.2.0",)], ("value",))
        if statement.strip().startswith("SELECT m.vehicle_id"):
            return ([("model",)], ("id",))
        return ([], ())

    raw._responses = vehicle_responses
    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.read_transport_capabilities",
        lambda connection: {},
    )
    vehicle = PostgresVehicleCatalogue("postgresql://example/db")
    monkeypatch.setattr(vehicle, "_read_model", lambda row, caps: row["id"])
    assert vehicle.list_models() == ("model",)


def test_postgres_catalogue_failure_contracts(monkeypatch):
    raw = FakeConnection()

    @contextmanager
    def fake_connect(*args, **kwargs):
        del args, kwargs
        yield raw

    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.psycopg.connect", fake_connect
    )
    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.read_world_snapshot",
        lambda connection: (_ for _ in ()).throw(ValueError("invalid")),
    )
    with pytest.raises(WorldCatalogueError):
        PostgresWorldCatalogue("postgresql://example/db").read()

    vehicle = PostgresVehicleCatalogue("postgresql://example/db")
    raw._responses = lambda statement, parameters: ([], ())
    with pytest.raises(CatalogueError):
        vehicle.list_models()

    def empty_vehicle(statement, parameters):
        del parameters
        if "catalog_metadata" in statement:
            return ([("2.2.0",)], ("value",))
        return ([], ())

    raw._responses = empty_vehicle
    monkeypatch.setattr(
        "app.repositories.postgres_catalogues.read_transport_capabilities",
        lambda connection: {},
    )
    with pytest.raises(CatalogueError):
        vehicle.list_models()


def test_postgres_backend_selection(tmp_path):
    sqlite_settings = make_settings(tmp_path)
    sqlite = build_game_database(sqlite_settings)
    assert isinstance(sqlite, SqliteGameDatabase)
    with (
        patch("app.bootstrap.PostgresGameDatabase") as postgres,
        patch("app.bootstrap.PostgresVehicleCatalogue") as vehicles,
        patch("app.bootstrap.PostgresWorldCatalogue") as world,
    ):
        configured = make_settings(tmp_path, "postgresql://example/db")
        build_game_database(configured)
        build_vehicle_catalogue(configured)
        build_world_catalogue(configured)
        postgres.assert_called_once_with("postgresql://example/db", "game", 5)
        vehicles.assert_called_once_with(
            "postgresql://example/db", "vehicle_catalogue"
        )
        world.assert_called_once_with(
            "postgresql://example/db", "world_catalogue"
        )


def test_sqlite_close_is_noop(tmp_path):
    database = SqliteGameDatabase(tmp_path / "game.db")
    assert database.close() is None

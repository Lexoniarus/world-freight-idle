"""PostgreSQL adapter for the existing repository SQL boundary."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, cast

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.pq import TransactionStatus
from psycopg_pool import ConnectionPool, PoolTimeout

from app.domain.errors import PersistenceError, UnsupportedGameSchema
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION

LOGGER = logging.getLogger(__name__)
_WRITER_LOCK = "world-freight-idle:game-writer:v1"
_SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RUNTIME_TABLES = {
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
_OBJECT_JSON_PATHS = {
    "$.data.contract",
    "$.data.origin",
    "$.data.destination",
    "$.data.dispatch_route.start",
    "$.data.journey",
    "$.data.cost_breakdown",
}
_INTEGER_JSON_PATHS = {
    "$.version",
    "$.data.payout_eur",
    "$.data.operating_cost_eur",
}
_NUMBER_JSON_PATHS = {
    "$.data.contract.tons",
    "$.data.route.distance_km",
    "$.data.route.duration_seconds",
    "$.data.dispatch_route.approach.distance_km",
    "$.data.departed_at",
    "$.data.arrives_at",
}
_JSON_EXTRACT = re.compile(
    r"json_extract\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*"
    r"'([^']+)'\s*\)",
    re.IGNORECASE,
)
_JSON_TYPE = re.compile(
    r"json_type\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*"
    r"'([^']+)'\s*\)",
    re.IGNORECASE,
)


def require_schema_name(value: str) -> str:
    """Reject schema names that cannot safely enter a PostgreSQL option."""
    if not _SCHEMA_NAME.fullmatch(value):
        raise ValueError("Invalid PostgreSQL schema name.")
    return value


def _json_path(path: str) -> str:
    """Convert a simple SQLite JSON path into PostgreSQL path notation."""
    if not path.startswith("$."):
        raise ValueError("Unsupported JSON path.")
    return "{" + ",".join(path[2:].split(".")) + "}"


def _json_extract_sql(column: str, path: str) -> str:
    """Preserve SQLite json_extract scalar/object semantics in PostgreSQL."""
    pg_path = _json_path(path)
    if path in _OBJECT_JSON_PATHS:
        return f"NULLIF((({column})::jsonb #> '{pg_path}')::text, 'null')"
    if path in _INTEGER_JSON_PATHS:
        return f"((({column})::jsonb #>> '{pg_path}')::bigint)"
    if path in _NUMBER_JSON_PATHS:
        return f"((({column})::jsonb #>> '{pg_path}')::double precision)"
    return f"(({column})::jsonb #>> '{pg_path}')"


def _json_type_sql(column: str, path: str) -> str:
    """Expose SQLite-compatible integer/real labels for JSON numbers."""
    pg_path = _json_path(path)
    value = f"(({column})::jsonb #> '{pg_path}')"
    text = f"(({column})::jsonb #>> '{pg_path}')"
    if path == "$.version":
        return (
            "CASE WHEN jsonb_typeof(" + value + ")='number' THEN 'integer' "
            "ELSE jsonb_typeof(" + value + ") END"
        )
    return (
        "CASE WHEN jsonb_typeof(" + value + ")='number' THEN "
        "CASE WHEN " + text + " ~ '^-?[0-9]+$' THEN 'integer' "
        "ELSE 'real' END ELSE jsonb_typeof(" + value + ") END"
    )


def translate_sql(statement: str) -> str | None:
    """Translate the small SQLite dialect used by runtime repositories."""
    stripped = statement.strip()
    upper = stripped.upper()
    if upper.startswith(
        ("PRAGMA ", "CREATE TABLE", "CREATE INDEX", "CREATE TRIGGER")
    ):
        return None
    if "FROM SQLITE_MASTER" in upper:
        return (
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema=current_schema()"
        )
    translated = re.sub(
        r"\bBEGIN\s+IMMEDIATE\b",
        "BEGIN",
        statement,
        flags=re.IGNORECASE,
    )
    translated = _JSON_EXTRACT.sub(
        lambda match: _json_extract_sql(match.group(1), match.group(2)),
        translated,
    )
    translated = _JSON_TYPE.sub(
        lambda match: _json_type_sql(match.group(1), match.group(2)),
        translated,
    )
    translated = re.sub(r"(?<!%)%(?![%sbt])", "%%", translated)
    translated = translated.replace("?", "%s")
    translated = re.sub(
        r"SELECT\s+value\s+FROM\s+json_each\(%s\)",
        "SELECT value FROM jsonb_array_elements_text(%s::jsonb) "
        "AS item(value)",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"SUM\(status='([^']+)'\)",
        r"SUM((status='\1')::integer)",
        translated,
        flags=re.IGNORECASE,
    )
    if re.search(r"ORDER\s+BY\s+rowid", translated, re.IGNORECASE):
        if re.search(r"FROM\s+owned_vehicles\b", translated, re.IGNORECASE):
            order = "vehicle_id"
        elif re.search(r"FROM\s+contract_offers\b", translated, re.IGNORECASE):
            order = "created_at, contract_id"
        elif re.search(r"FROM\s+transports\b", translated, re.IGNORECASE):
            order = "departed_at, transport_id"
        elif re.search(
            r"FROM\s+market_templates\b", translated, re.IGNORECASE
        ):
            order = "template_id"
        else:
            raise ValueError("Unsupported SQLite rowid ordering.")
        translated = re.sub(
            r"ORDER\s+BY\s+rowid",
            "ORDER BY " + order,
            translated,
            flags=re.IGNORECASE,
        )
    return translated


class HybridRow:
    """Expose PostgreSQL rows by column name and by positional index."""

    def __init__(self, names: Sequence[str], values: Sequence[Any]) -> None:
        self._names = tuple(names)
        self._values = tuple(values)
        self._mapping = dict(zip(self._names, self._values, strict=True))

    def keys(self) -> tuple[str, ...]:
        """Support ``dict(row)`` like sqlite3.Row."""
        return self._names

    def __getitem__(self, key: str | int) -> Any:
        """Read by SQL column name or positional index."""
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self) -> Iterator[Any]:
        """Iterate positional values like sqlite3.Row."""
        return iter(self._values)

    def __len__(self) -> int:
        """Return the number of projected columns."""
        return len(self._values)


class PostgresCursorAdapter:
    """Project psycopg tuples through the sqlite3.Row access contract."""

    def __init__(self, cursor: Any | None = None) -> None:
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        """Expose affected rows for lease acquisition and guarded updates."""
        return 0 if self._cursor is None else int(self._cursor.rowcount)

    def _names(self) -> tuple[str, ...]:
        if self._cursor is None or self._cursor.description is None:
            return ()
        return tuple(column.name for column in self._cursor.description)

    def _row(self, values: Sequence[Any] | None) -> HybridRow | None:
        if values is None:
            return None
        return HybridRow(self._names(), values)

    def fetchone(self) -> HybridRow | None:
        """Fetch one hybrid row, or None."""
        if self._cursor is None:
            return None
        return self._row(self._cursor.fetchone())

    def fetchall(self) -> list[HybridRow]:
        """Fetch all rows while preserving positional and named access."""
        if self._cursor is None:
            return []
        names = self._names()
        return [HybridRow(names, row) for row in self._cursor.fetchall()]

    def __iter__(self) -> Iterator[HybridRow]:
        """Stream hybrid rows from the underlying cursor."""
        if self._cursor is None:
            return iter(())
        names = self._names()
        return (HybridRow(names, row) for row in self._cursor)


class PostgresConnectionAdapter:
    """Translate repository SQL and expose the subset of sqlite API in use."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(
        self, statement: str, parameters: Sequence[Any] = ()
    ) -> PostgresCursorAdapter:
        """Execute one translated statement without leaking driver rows."""
        translated = translate_sql(statement)
        if translated is None:
            return PostgresCursorAdapter()
        cursor = self._connection.cursor()
        try:
            cursor.execute(cast(Any, translated), parameters)
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        return PostgresCursorAdapter(cursor)

    def executemany(
        self, statement: str, parameters: Sequence[Sequence[Any]]
    ) -> PostgresCursorAdapter:
        """Execute a translated batch in the caller's transaction."""
        translated = translate_sql(statement)
        if translated is None:
            return PostgresCursorAdapter()
        cursor = self._connection.cursor()
        try:
            cursor.executemany(cast(Any, translated), parameters)
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        return PostgresCursorAdapter(cursor)

    def executescript(self, script: str) -> None:
        """Ignore SQLite DDL; production schema is migration-owned."""
        del script

    def commit(self) -> None:
        """Commit an explicitly opened read transaction when present."""
        if self._connection.info.transaction_status == TransactionStatus.IDLE:
            return
        if self._connection.autocommit:
            self._connection.execute("COMMIT")
        else:
            self._connection.commit()

    def rollback(self) -> None:
        """Rollback an explicitly opened transaction when present."""
        if self._connection.info.transaction_status == TransactionStatus.IDLE:
            return
        if self._connection.autocommit:
            self._connection.execute("ROLLBACK")
        else:
            self._connection.rollback()


class PostgresGameDatabase(SqliteGameDatabase):
    """Own pooled PostgreSQL connections while preserving repository ports."""

    def __init__(
        self,
        database_url: str,
        schema: str = "game",
        pool_size: int = 5,
    ) -> None:
        self.schema = require_schema_name(schema)
        self._postgres_active: ContextVar[PostgresConnectionAdapter | None] = (
            ContextVar(
                "postgres_game_transaction",
                default=None,
            )
        )
        conninfo = make_conninfo(
            database_url,
            options=f"-csearch_path={self.schema},public",
            application_name="world-freight-idle",
            connect_timeout=10,
        )
        self._pool = ConnectionPool(
            conninfo,
            min_size=1,
            max_size=max(1, pool_size),
            kwargs={"autocommit": True, "prepare_threshold": None},
        )

    @contextmanager
    def connect(  # type: ignore[override]
        self,
    ) -> Iterator[PostgresConnectionAdapter]:
        """Reuse the active UoW connection or borrow one pooled connection."""
        active = self._postgres_active.get()
        if active is not None:
            yield active
            return
        try:
            with self._pool.connection() as connection:
                connection.execute(
                    cast(Any, f"SET search_path TO {self.schema}, public")
                )
                yield PostgresConnectionAdapter(connection)
        except (psycopg.Error, PoolTimeout, sqlite3.Error) as exc:
            LOGGER.error(
                "Game persistence operation failed",
                extra={"event": "state.persistence_error"},
            )
            raise PersistenceError("Spielstand nicht verfügbar.") from exc

    @contextmanager
    def read_transaction(self) -> Iterator[None]:
        """Hold one repeatable, read-only PostgreSQL snapshot."""
        if self._postgres_active.get() is not None:
            yield
            return
        try:
            with self._pool.connection() as connection:
                connection.execute(
                    cast(Any, f"SET search_path TO {self.schema}, public")
                )
                connection.autocommit = False
                connection.execute(
                    "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ "
                    "READ ONLY"
                )
                adapter = PostgresConnectionAdapter(connection)
                token = self._postgres_active.set(adapter)
                try:
                    yield
                finally:
                    connection.rollback()
                    self._postgres_active.reset(token)
                    connection.autocommit = True
        except (psycopg.Error, PoolTimeout) as exc:
            raise PersistenceError("Spielstand nicht verfügbar.") from exc

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Serialize writers like BEGIN IMMEDIATE and commit one outer UoW."""
        if self._postgres_active.get() is not None:
            yield
            return
        try:
            with self._pool.connection() as connection:
                connection.execute(
                    cast(Any, f"SET search_path TO {self.schema}, public")
                )
                connection.autocommit = False
                connection.execute("BEGIN")
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (_WRITER_LOCK,),
                )
                adapter = PostgresConnectionAdapter(connection)
                token = self._postgres_active.set(adapter)
                try:
                    yield
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
                finally:
                    self._postgres_active.reset(token)
                    connection.autocommit = True
        except (psycopg.Error, PoolTimeout) as exc:
            raise PersistenceError("Spielstand nicht verfügbar.") from exc

    def initialize(self) -> None:
        """Require the already migrated Supabase schema and its safeguards."""
        with self.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema=%s",
                    (self.schema,),
                )
            }
            if not _RUNTIME_TABLES.issubset(tables):
                raise UnsupportedGameSchema(
                    "PostgreSQL-Spielstandschema ist unvollständig."
                )
            versions = connection.execute(
                "SELECT version FROM game_schema"
            ).fetchall()
            if [row[0] for row in versions] != [VERSION]:
                raise UnsupportedGameSchema("Unbekannte Spielstandversion.")
            index = connection.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname=%s "
                "AND indexname='one_active_transport_per_vehicle'",
                (self.schema,),
            ).fetchone()
            trigger = connection.execute(
                "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=%s AND c.relname='transports' "
                "AND t.tgname='retain_settlement' AND NOT t.tgisinternal",
                (self.schema,),
            ).fetchone()
            if index is None or trigger is None:
                raise UnsupportedGameSchema(
                    "PostgreSQL-Spielstandschutz ist unvollständig."
                )
        LOGGER.info(
            "PostgreSQL game schema validated",
            extra={
                "event": "state.schema_validated",
                "data": {"schema_version": VERSION, "backend": "postgres"},
            },
        )

    def close(self) -> None:
        """Release all pooled PostgreSQL connections owned by this process."""
        self._pool.close()

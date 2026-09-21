"""SQLite persistence for game state and provider caches."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geocode_cache (
    address TEXT PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    display_name TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS route_cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


class SqliteStore:
    """Small repository used by the MVP application services."""

    def __init__(
        self,
        path: Path,
        namespace: str = "",
        initialize_schema: bool = True,
    ) -> None:
        self.path = path
        self.namespace = namespace
        self._connection: ContextVar[sqlite3.Connection | None] = ContextVar(
            "transaction_connection",
            default=None,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if initialize_schema:
            self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured SQLite connection and always close it."""
        active = self._connection.get()
        if active is not None:
            yield active
            return
        connection = sqlite3.connect(
            self.path,
            timeout=15,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit an entire synchronous use case or roll it back on failure."""
        if self._connection.get() is not None:
            yield
            return
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            token = self._connection.set(connection)
            try:
                yield
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                self._connection.reset(token)

    def initialize(self) -> None:
        """Create required tables if they do not already exist."""
        with self.connect() as connection:
            connection.executescript(_SCHEMA)

    def has_json(self, key: str) -> bool:
        """Check key existence without decoding its JSON payload."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM kv WHERE key = ?",
                (self.namespace + key,),
            ).fetchone()
        return row is not None

    def get_json(self, key: str, default: Any = None) -> Any:
        """Read a JSON value from the key-value state table."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM kv WHERE key = ?",
                (self.namespace + key,),
            ).fetchone()
        return default if row is None else json.loads(row["value"])

    def set_json(self, key: str, value: Any) -> None:
        """Persist a JSON-serializable value under a stable key."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO kv(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (self.namespace + key, json.dumps(value)),
            )

    def delete_state_keys(self, keys: tuple[str, ...]) -> None:
        """Delete selected game-state keys without touching provider caches."""
        with self.connect() as connection:
            connection.executemany(
                "DELETE FROM kv WHERE key = ?",
                ((self.namespace + key,) for key in keys),
            )

    def get_geocode(self, address: str) -> dict[str, Any] | None:
        """Return a cached geocode entry if one exists."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM geocode_cache WHERE address = ?",
                (address,),
            ).fetchone()
        return dict(row) if row else None

    def put_geocode(
        self,
        address: str,
        lat: float,
        lon: float,
        display_name: str,
    ) -> None:
        """Insert or replace one cached geocoding result."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO geocode_cache(
                    address, lat, lon, display_name, updated_at
                ) VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    lat = excluded.lat,
                    lon = excluded.lon,
                    display_name = excluded.display_name,
                    updated_at = excluded.updated_at
                """,
                (address, lat, lon, display_name, time.time()),
            )

    def get_route(self, cache_key: str) -> dict[str, Any] | None:
        """Return a cached routed path if present."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM route_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def put_route(self, cache_key: str, payload: dict[str, Any]) -> None:
        """Insert or replace one route cache entry."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO route_cache(cache_key, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (cache_key, json.dumps(payload), time.time()),
            )
